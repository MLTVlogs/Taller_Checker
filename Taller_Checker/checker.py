from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
from multimethod import multimeta

from symtab import Symtab
from model import *

	
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
			self.error(node, f"redeclaración de '{name}' en el mismo alcance")
		except Symtab.SymbolConflictError:
			self.error(node, f"conflicto de símbolo '{name}'")
			
	def lookup(self, node, name: str):
		sym = self.symtab.get(name) if self.symtab else None
		if sym is None:
			self.error(node, f"símbolo '{name}' no definido")
		return sym
		
	def ok(self) -> bool:
		return len(self.errors) == 0
		
	# -------------------------------------------------
	# Visitor methods
	# -------------------------------------------------
	
	def visit(self, n: Program):
		for decl in n.decls:
			decl.accept(self)
			
	def visit(self, n: Block):
		self.open_scope("block")
		for stmt in n.stmts:
			stmt.accept(self)
		self.close_scope()
		
	def visit(self, n: VarDecl):
		sym = Symbol(
		name=n.name,
		kind="var",
		type=n.type,
		node=n,
		mutable=getattr(n, "mutable", True),
		)
		self.define(n, n.name, sym)
		
		if getattr(n, "value", None) is not None:
			n.value.accept(self)
			
	def visit(self, n: ConstDecl):
		sym = Symbol(
			name=n.name,
			kind="var",
			type=n.type,
			node=n,
			mutable=False,
		)
		self.define(n, n.name, sym)
		
		if getattr(n, "value", None) is not None:
			n.value.accept(self)
			
	def visit(self, n: Param):
		sym = Symbol(
			name=n.name,
			kind="param",
			type=n.type,
			node=n,
			mutable=True,
		)
		self.define(n, n.name, sym)
		
	def visit(self, n: FuncDecl):
		# Registrar la función en el scope actual
		fsym = Symbol(
			name=n.name,
			kind="func",
			type=n.type,     # puede ser solo retorno o una firma más completa
			node=n,
			mutable=False,
		)
		self.define(n, n.name, fsym)
		
		old_function = self.current_function
		self.current_function = n
		
		self.open_scope(f"function {n.name}")
		
		parms = getattr(n, "parms", None)
		if parms is not None:
			params = getattr(parms, "params", parms)
			for p in params:
				p.accept(self)
				
		if getattr(n, "body", None) is not None:
			n.body.accept(self)
			
		self.close_scope()
		self.current_function = old_function
		
	def visit(self, n: Assignment):
		n.loc.accept(self)
		n.expr.accept(self)
		
	def visit(self, n: PrintStmt):
		if getattr(n, "expr", None) is not None:
			n.expr.accept(self)
			
	def visit(self, n: IfStmt):
		n.test.accept(self)
		n.then_block.accept(self)
		if getattr(n, "else_block", None) is not None:
			n.else_block.accept(self)
			
	def visit(self, n: WhileStmt):
		n.test.accept(self)
		n.body.accept(self)
		
	def visit(self, n: ForStmt):
		if getattr(n, "init", None) is not None:
			n.init.accept(self)
		if getattr(n, "test", None) is not None:
			n.test.accept(self)
		if getattr(n, "step", None) is not None:
			n.step.accept(self)
		if getattr(n, "body", None) is not None:
			n.body.accept(self)
			
	def visit(self, n: ReturnStmt):
		if getattr(n, "expr", None) is not None:
			n.expr.accept(self)
			
	def visit(self, n: VarLoc):
		sym = self.lookup(n, n.name)
		n.sym = sym
		n.type = sym.type if sym else None
		
	def visit(self, n: FuncCall):
		sym = self.lookup(n, n.name)
		if sym is not None and sym.kind != "func":
			self.error(n, f"'{n.name}' no es una función")
			
		args = getattr(n, "args", None)
		if args is not None:
			exprs = getattr(args, "exprs", args)
			for arg in exprs:
				arg.accept(self)
				
		n.sym = sym
		n.type = sym.type if sym else None
		
	def visit(self, n: BinOp):
		n.left.accept(self)
		n.right.accept(self)
		
	def visit(self, n: UnaryOp):
		n.expr.accept(self)
		
	def visit(self, n: IntegerLiteral):
		n.type = "integer"
		
	def visit(self, n: BooleanLiteral):
		n.type = "boolean"
		
	def visit(self, n: StringLiteral):
		n.type = "string"


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