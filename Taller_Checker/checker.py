from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
from multimethod import multimeta

from symtab import Symtab
from model import *
from typesys import check_binop, check_unaryop

	
@dataclass
class Symbol:
	name: str
	kind: str          # var, param, func
	type: Any
	node: Any = None
	mutable: bool = True
	
	def __repr__(self):
		return f"Symbol(name={self.name!r}, kind={self.kind!r}, type={self.type!r})"
		
class Visitor():
    def visit(self, node):
        method_name = 'visit_' + node.__class__.__name__
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node):
        print(f"visitando nodo no definido: {node.__class__.__name__}")
        pass
		
class Checker(Visitor):
	def __init__(self):
		self.errors: list[str] = []
		self.symtab: Optional[Symtab] = None
		self.current_function = None
		
	# -------------------------------------------------
	# Punto de entrada
	# -------------------------------------------------
	@classmethod
	def check(cls, node):
		checker = cls()
		checker.open_scope("global")
		node.accept(checker)
		return checker
		
	# -------------------------------------------------
	# Utilidades
	# -------------------------------------------------
	def error(self, node, message: str):
		lineno = getattr(node, "lineno", "?")
		self.errors.append(f"error:{lineno}: {message}")
		
	def open_scope(self, name: str):
		if self.symtab is None:
			self.symtab = Symtab(name)
		else:
			self.symtab = Symtab(name, parent=self.symtab)
			
	def close_scope(self):
		if self.symtab is not None:
			self.symtab = self.symtab.parent
			
	def define(self, node, name: str, symbol: Symbol):
		try:
			self.symtab.add(name, symbol)
		except Symtab.SymbolDefinedError:
			self.error(node, f"redeclaración de '{name}' en el mismo alcance")
		except Symtab.SymbolConflictError:
			self.error(node, f"conflicto de símbolo '{name}'")
			
	def lookup(self, node, name: str):
		sym = self.symtab.get(name) if self.symtab else None
		if sym is None:
			self.error(node, f"símbolo '{name}' no definido")
		return sym
		
	def ok(self):
		return len(self.errors) == 0
	
	# -------------------------------------------------
	# Utilidades para tipos
	# -------------------------------------------------
	def type_to_string(self, typ: Any) -> str:
		"""Convierte un tipo a una representación legible en string."""
		if hasattr(typ, 'name'):
			# SimpleType
			return typ.name
		elif hasattr(typ, 'elem'):
			# ArrayType o ArraySizedType
			if hasattr(typ, 'size_expr'):
				return f"array[*] {self.type_to_string(typ.elem)}"
			else:
				return f"array[] {self.type_to_string(typ.elem)}"
		elif hasattr(typ, 'ret'):
			# FuncType
			params = ', '.join(self.type_to_string(p.typ) for p in typ.params) if typ.params else ''
			return f"function {self.type_to_string(typ.ret)} ({params})"
		else:
			return str(typ)
	
	def types_compatible(self, typ1: Any, typ2: Any) -> bool:
		"""Verifica si dos tipos son compatibles para asignación."""
		# Si ambos son el mismo tipo, son compatibles
		if typ1 == typ2:
			return True
		
		# SimpleType
		if hasattr(typ1, 'name') and hasattr(typ2, 'name'):
			# Mismos nombres
			return typ1.name == typ2.name
		
		# ArrayType
		if hasattr(typ1, 'elem') and hasattr(typ2, 'elem'):
			# Mismo tipo de elemento
			return self.types_compatible(typ1.elem, typ2.elem)
		
		return False
		
	# -------------------------------------------------
	# Visitor methods
	# -------------------------------------------------
	
	def visit_Program(self, n):
		for decl in n.decls:
			decl.accept(self)
			
	def visit_Block(self, n):
		self.open_scope("block")
		for stmt in n.stmts:
			stmt.accept(self)
		self.close_scope()
		
	def visit_DeclTyped(self, n):
		# Detectar si el tipo es FuncType (función sin implementación/declaración)
		is_func = hasattr(n.typ, 'params') and n.typ.__class__.__name__ == 'FuncType'
		
		kind = "func" if is_func else "var"
		sym = Symbol(
			name=n.name,
			kind=kind,
			type=n.typ,
			node=n,
			mutable=not is_func,
		)
		self.define(n, n.name, sym)
		
	def visit_Param(self, n):
		sym = Symbol(
			name=n.name,
			kind="param",
			type=n.typ,
			node=n,
			mutable=True,
		)
		self.define(n, n.name, sym)
		
	def visit_DeclInit(self, n):
		# Registrar la función o variable en el scope actual
		init_value = getattr(n, "init", None)
		
		# Detectar si es una función: si el tipo es FuncType OR si init es una lista
		is_func = hasattr(n.typ, 'params') and n.typ.__class__.__name__ == 'FuncType'
		
		if is_func:
			# Es una función
			fsym = Symbol(
				name=n.name,
				kind="func",
				type=n.typ,
				node=n,
				mutable=False,
			)
			self.define(n, n.name, fsym)
			
			old_function = self.current_function
			self.current_function = n
			
			self.open_scope(f"function {n.name}")
			
			# Registrar los parámetros de la función si existen
			if n.typ.params:
				for param in n.typ.params:
					# Los parámetros no tienen accept(), registrar directamente
					psym = Symbol(
						name=param.name,
						kind="param",
						type=param.typ,
						node=param,
						mutable=True,
					)
					self.define(param, param.name, psym)
			
			# Procesar el cuerpo de la función
			if init_value is not None:
				if isinstance(init_value, list):
					# Es una lista de statements
					for stmt in init_value:
						if hasattr(stmt, 'accept'):
							stmt.accept(self)
				elif hasattr(init_value, 'accept'):
					# Es un Block u otro nodo con accept
					init_value.accept(self)
			
			self.close_scope()
			self.current_function = old_function
		else:
			# Es una variable
			sym = Symbol(
				name=n.name,
				kind="var",
				type=n.typ,
				node=n,
				mutable=False,
			)
			self.define(n, n.name, sym)
			
			if init_value is not None:
				# Puede ser una lista (arreglo) o un objeto con accept
				if isinstance(init_value, list):
					# Primero procesar todos los items para asignarles tipos
					for item in init_value:
						if hasattr(item, 'accept'):
							item.accept(self)
					
					# Luego validar compatibilidad de tipos
					for item in init_value:
						if hasattr(item, 'type'):
							elem_type = n.typ.elem if hasattr(n.typ, 'elem') else n.typ
							if not self.types_compatible(elem_type, item.type):
								elem_str = self.type_to_string(elem_type)
								item_str = self.type_to_string(item.type)
								self.error(n, f"elemento incompatible: esperado {elem_str} pero obtuvo {item_str}")
								
				elif hasattr(init_value, 'accept'):
					# Inicializador de variable simple
					init_value.accept(self)
					# Validar compatibilidad de tipo
					if hasattr(init_value, 'type'):
						if not self.types_compatible(n.typ, init_value.type):
							expected = self.type_to_string(n.typ)
							got = self.type_to_string(init_value.type)
							self.error(n, f"inicializador incompatible: esperado {expected} pero obtuvo {got}")
		
	def visit_Assign(self, n):
		n.target.accept(self)
		n.value.accept(self)
		
		# Validar compatibilidad de tipos en asignación
		if hasattr(n.target, 'type') and hasattr(n.value, 'type'):
			if not self.types_compatible(n.target.type, n.value.type):
				target_str = self.type_to_string(n.target.type)
				value_str = self.type_to_string(n.value.type)
				self.error(n, f"asignación incompatible: esperado {target_str} pero obtuvo {value_str}")
		
	def visit_Print(self, n):
		if getattr(n, "values", None) is not None:
			for expr in n.values:
				expr.accept(self)
			
	def visit_If(self, n):
		if n.cond is not None:
			n.cond.accept(self)
			# Validar que la condición sea boolean
			if hasattr(n.cond, 'type'):
				cond_type = self.type_to_string(n.cond.type)
				if cond_type != 'boolean':
					self.error(n, f"condición debe ser boolean pero obtuvo {cond_type}")
		
		n.then.accept(self)
		if getattr(n, "otherwise", None) is not None:
			n.otherwise.accept(self)
			
	def visit_While(self, n):
		if n.cond is not None:
			n.cond.accept(self)
			# Validar que la condición sea boolean
			if hasattr(n.cond, 'type'):
				cond_type = self.type_to_string(n.cond.type)
				if cond_type != 'boolean':
					self.error(n, f"condición debe ser boolean pero obtuvo {cond_type}")
		
		n.body.accept(self)
		
	def visit_For(self, n):
		if getattr(n, "init", None) is not None:
			n.init.accept(self)
		if getattr(n, "cond", None) is not None:
			n.cond.accept(self)
			# Validar que la condición sea boolean
			if hasattr(n.cond, 'type'):
				cond_type = self.type_to_string(n.cond.type)
				if cond_type != 'boolean':
					self.error(n, f"condición debe ser boolean pero obtuvo {cond_type}")
		if getattr(n, "step", None) is not None:
			n.step.accept(self)
		if getattr(n, "body", None) is not None:
			n.body.accept(self)
			
	def visit_Return(self, n):
		# Validar tipo de retorno
		if self.current_function is not None:
			func_type = self.current_function.typ
			if hasattr(func_type, 'ret'):
				return_type = func_type.ret
				is_void = hasattr(return_type, 'name') and return_type.name == 'void'
				
				has_value = getattr(n, "value", None) is not None
				
				if is_void and has_value:
					self.error(n, f"función con retorno void no puede retornar un valor")
				elif not is_void and not has_value:
					type_str = self.type_to_string(return_type)
					self.error(n, f"función debe retornar un valor de tipo {type_str}")
		
		if getattr(n, "value", None) is not None:
			n.value.accept(self)
			
	def visit_Name(self, n):
		sym = self.lookup(n, n.id)
		n.sym = sym
		n.type = sym.type if sym else None
		
	def visit_Call(self, n):
		sym = self.lookup(n, n.func)
		if sym is not None and sym.kind != "func":
			self.error(n, f"'{n.func}' no es una función")
			
		args = getattr(n, "args", None)
		if args is not None:
			for arg in args:
				arg.accept(self)
			
			# Validar número y tipos de argumentos
			if sym is not None and sym.kind == "func":
				func_type = sym.type
				if hasattr(func_type, 'params'):
					expected_params = func_type.params
					
					# Validar número de argumentos
					if len(args) != len(expected_params):
						self.error(n, f"'{n.func}' esperaba {len(expected_params)} argumentos pero obtuvo {len(args)}")
					else:
						# Validar tipos de argumentos
						for i, (arg, param) in enumerate(zip(args, expected_params)):
							if hasattr(arg, 'type'):
								if not self.types_compatible(param.typ, arg.type):
									param_str = self.type_to_string(param.typ)
									arg_str = self.type_to_string(arg.type)
									self.error(n, f"argumento {i+1} incompatible: esperado {param_str} pero obtuvo {arg_str}")
				
		n.sym = sym
		# Asignar el tipo de retorno de la función, no el tipo de la función completa
		if sym is not None and hasattr(sym.type, 'ret'):
			n.type = sym.type.ret
		else:
			n.type = None
		
	def visit_BinOp(self, n):
		n.left.accept(self)
		n.right.accept(self)
		
		# Validar operación
		if hasattr(n.left, 'type') and hasattr(n.right, 'type'):
			left_type_str = self.type_to_string(n.left.type)
			right_type_str = self.type_to_string(n.right.type)
			
			# Extraer nombre simple del tipo (sin decoradores de array)
			left_base = left_type_str.split('[')[0].strip()
			right_base = right_type_str.split('[')[0].strip()
			
			result_type = check_binop(n.op, left_base, right_base)
			if result_type is None:
				self.error(n, f"operación inválida: {left_type_str} {n.op} {right_type_str}")
			else:
				# Convertir string a SimpleType
				n.type = SimpleType(result_type)
		
	def visit_UnaryOp(self, n):
		n.expr.accept(self)
		
		# Validar operación unaria
		if hasattr(n.expr, 'type'):
			expr_type_str = self.type_to_string(n.expr.type)
			expr_base = expr_type_str.split('[')[0].strip()
			
			result_type = check_unaryop(n.op, expr_base)
			if result_type is None:
				self.error(n, f"operación unaria inválida: {n.op}{expr_type_str}")
			else:
				# Convertir string a SimpleType
				n.type = SimpleType(result_type)
		
	def visit_Literal(self, n):
		# Mapeo de tipos según el kind
		kind_to_type = {
			"int": "integer",
			"float": "float",
			"char": "char",
			"string": "string",
			"bool": "boolean",
			"integer": "integer",
			"boolean": "boolean",
		}
		type_name = kind_to_type.get(n.kind, n.kind)
		# Asignar como SimpleType, no como string
		n.type = SimpleType(type_name)
	
	def visit_Index(self, n):
		if hasattr(n, 'base') and hasattr(n.base, 'accept'):
			n.base.accept(self)
		if hasattr(n, 'indices'):
			for idx in n.indices:
				if hasattr(idx, 'accept'):
					idx.accept(self)
	
	def visit_MemberCall(self, n):
		if hasattr(n, 'members'):
			for member in n.members:
				if hasattr(member, 'accept'):
					member.accept(self)
	
	def visit_TernOp(self, n):
		n.cond.accept(self)
		n.then.accept(self)
		n.otherwise.accept(self)
	
	def visit_PrefixOp(self, n):
		if hasattr(n, 'expr') and hasattr(n.expr, 'accept'):
			n.expr.accept(self)
	
	def visit_PostfixOp(self, n):
		if hasattr(n, 'expr'):
			expr = n.expr
			# Defensa contra parser que pasa argumentos en orden incorrecto
			if not hasattr(expr, 'accept') and hasattr(n, 'op') and hasattr(n.op, 'accept'):
				# Si expr es un string y op tiene accept, intercambiar
				expr = n.op
			if hasattr(expr, 'accept'):
				expr.accept(self)
	
	def visit_Constructor(self, n):
		if hasattr(n, 'atts'):
			for att in n.atts:
				if hasattr(att, 'accept'):
					att.accept(self)
	
	def visit_ExprStmt(self, n):
		n.expr.accept(self)
	
	def visit_ClassDecl(self, n):
		if hasattr(n, 'body') and n.body:
			for member in n.body:
				if hasattr(member, 'accept'):
					member.accept(self)
	
	def visit_Break(self, n):
		pass
	
	def visit_Continue(self, n):
		pass

if __name__ == "__main__":
    import sys
    from parser import parse

    if len(sys.argv) != 2:
        print("Uso: python checker.py <archivo.bminor>")
        sys.exit(1)

    filename = sys.argv[1]
    with open(filename, encoding="utf-8") as f:
        txt = f.read()
        ast = parse(txt)
        checker = Checker.check(ast)
        if checker.ok():
            print("No se encontraron errores semánticos.")
        else:
            print("Errores semánticos encontrados:")
            for err in checker.errors:
                print(err)