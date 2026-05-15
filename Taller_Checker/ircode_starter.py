from __future__ import annotations
#IMPORTANTE!!!!!!!!!!!!!! todo esta escrito de la forma **opcode reg1 reg2 destino** no confundir el orden porque si no queda mal hecho todo esto
#el orden viene desde la plantilla del profesor

from dataclasses import dataclass, field
from typing import Optional
from rich import print

from model import *
from checker import *

# ===================================================
# Type constants
# ===================================================
# Definir constantes de tipos comunes para IRCodeGen
VOID = SimpleType('void')
INT = SimpleType('integer')
BOOL = SimpleType('boolean')
CHAR = SimpleType('char')
STRING = SimpleType('string')

# Aliases para compatibilidad
IntegerType = SimpleType
BooleanType = SimpleType
CharType = SimpleType
VoidType = SimpleType

# ===================================================
# IR model
# ===================================================

Instruction = tuple


@dataclass
class Storage:
    """
    Describe dónde vive un símbolo durante la generación de IR.

    El objetivo es que el estudiante tenga una estructura simple para
    consultar tipo y categoría del símbolo (global, parámetro, constante).
    """
    name: str
    ty: Type
    is_global: bool = False
    is_param: bool = False
    is_const: bool = False


@dataclass
class IRFunction:
    name: str
    params: list[tuple[str, Type]]
    return_type: Type
    instructions: list[Instruction] = field(default_factory=list)


@dataclass
class IRProgram:
    globals: list[Instruction] = field(default_factory=list)
    functions: list[IRFunction] = field(default_factory=list)

    def format(self) -> str:
        out: list[str] = []
        if self.globals:
            out.append("# Globals")
            for inst in self.globals:
                out.append(format_instruction(inst))
            out.append("")

        for fn in self.functions:
            params = ", ".join(f"{name}:{ty}" for name, ty in fn.params)
            out.append(f"function {fn.name}({params}) -> {fn.return_type}")
            for inst in fn.instructions:
                out.append(f"  {format_instruction(inst)}")
            out.append("")
        return "\n".join(out).rstrip()


# ===================================================
# Pretty printing
# ===================================================


def format_instruction(inst: Instruction) -> str:
    op = inst[0]
    if len(inst) == 1:
        return op
    args = ", ".join(
        repr(x) if isinstance(x, str) and x.startswith("L") else str(x)
        for x in inst[1:]
    )
    return f"{op} {args}"


# ===================================================
# Generator
# ===================================================


class IRCodeGen(Visitor):
    """
    Plantilla base para el proyecto de IRCode.

    Esta versión deja aproximadamente la mitad del trabajo resuelto:

    Ya implementado:
    - estructura del programa IR
    - manejo de temporales y labels
    - scopes y lookup de símbolos
    - declaración de variables y constantes
    - carga de literales enteros, booleanos y chars
    - lectura de variables (Name)
    - impresión simple
    - retorno simple
    - parte de la selección de opcodes

    - completar UnaryOp
    - completar BinOp

    
    Pendiente para estudiantes:
    - completar Assign compuesto
    - completar If / While / For
    - completar Call
    - arreglos (Index) y strings
    - conversiones adicionales y mejoras del IR

    Sugerencia pedagógica:
    1. Hacer primero expresiones aritméticas.
    2. Luego comparaciones.
    3. Después control de flujo.
    4. Finalmente llamadas, arreglos y extensiones.
    """

    def __init__(self):
        self.program = IRProgram()
        self.current_function: Optional[IRFunction] = None
        self.current_return_type: Type = VOID
        self.temp_count = 0
        self.label_count = 0
        self.scopes: list[dict[str, Storage]] = []

        self.string_count = 0
        self.string_tabla = {}

        self.array_count = 0
        self.array_tabla = {}

        self.loop_actual: Optional[tuple[str, str]] = None  # (label_break, label_continue)

    @classmethod
    def generate(cls, node: Program) -> IRProgram:
        gen = cls()
        gen.visit(node)
        return gen.program

    def visit(self, node):
        """Dispatcher que redirige a visit_<NombreDelNodo> según el tipo."""
        if node is None:
            return None
        method_name = f"visit_{node.__class__.__name__}"
        method = getattr(self, method_name, None)
        if method is None:
            raise NotImplementedError(f"No visitor para {node.__class__.__name__}")
        return method(node)

    # -------------------------------------------------
    # helpers básicos
    # -------------------------------------------------

    def new_temp(self) -> str:
        self.temp_count += 1
        return f"R{self.temp_count}"

    def new_label(self, prefix: str = "L") -> str:
        self.label_count += 1
        return f"{prefix}{self.label_count}"

    def emit(self, *inst) -> None:
        inst = tuple(inst)
        if self.current_function is None:
            self.program.globals.append(inst)
        else:
            self.current_function.instructions.append(inst)

    def push_scope(self) -> None:
        self.scopes.append({})

    def pop_scope(self) -> None:
        self.scopes.pop()

    def bind(self, storage: Storage) -> None:
        if not self.scopes:
            self.push_scope()
        self.scopes[-1][storage.name] = storage

    def lookup(self, name: str) -> Storage:
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        raise NameError(f"Nombre no resuelto en IRCodeGen: {name}")

    def infer_type(self, node: Optional[Node]) -> Type:
        """
        Inferencia mínima para que el generador pueda escoger opcodes.

        Nota: aquí se asume que el checker semántico ya pasó antes.
        """
        if node is None:
            return VOID

        # Intentar obtener tipo del atributo "typ" o "type"
        ty = getattr(node, "typ", None)
        if ty is None:
            ty = getattr(node, "type", None)
        if isinstance(ty, Type):
            return ty

        if isinstance(node, Literal):
            if node.kind == "integer":
                return INT
            elif node.kind == "boolean":
                return BOOL
            elif node.kind == "char":
                return CHAR
            elif node.kind == "string":
                return STRING
        if isinstance(node, (DeclTyped, DeclInit, Param)):
            return node.typ

        # Valor por defecto conservador para no bloquear pruebas tempranas.
        return INT

    def type_suffix(self, ty: Type) -> str:
        #si es arreglo pues devuelve el tipo del arreglo, porque si no devolvia ArrayType y eso no sirve
        if isinstance(ty, (ArrayType, ArraySizedType)):
            return self.type_suffix(ty.elem)
        
        if isinstance(ty, (IntegerType, BooleanType)):
            return "I"
        if isinstance(ty, CharType):
            return "B"
        if isinstance(ty, VoidType):
            return "V"
        raise NotImplementedError(f"Tipo aún no soportado en esta plantilla: {ty}")

    def move_opcode(self, ty: Type) -> str:
        return f"MOV{self.type_suffix(ty)}"

    def load_opcode(self, ty: Type) -> str:
        return f"LOAD{self.type_suffix(ty)}"

    def store_opcode(self, ty: Type) -> str:
        return f"STORE{self.type_suffix(ty)}"

    def alloc_opcode(self, ty: Type) -> str:
        return f"ALLOC{self.type_suffix(ty)}"

    def var_opcode(self, ty: Type) -> str:
        return f"VAR{self.type_suffix(ty)}"

    def print_opcode(self, ty: Type) -> str:
        return f"PRINT{self.type_suffix(ty)}"

    def cmp_opcode(self, ty: Type) -> str:
        return f"CMP{self.type_suffix(ty)}"

    # -------------------------------------------------
    # opcodes auxiliares
    # -------------------------------------------------

    def binary_arith_opcode(self, oper: str, ty: Type) -> str:
        suffix = self.type_suffix(ty)
        table = {
            "+": f"ADD{suffix}",
            "-": f"SUB{suffix}",
            "*": f"MUL{suffix}",
            "/": f"DIV{suffix}",
        }
        if oper not in table:
            raise NotImplementedError(f"Aritmética no soportada: {oper}")
        return table[oper]
    
    def binary_cmp_opcode(self, oper: str, ty: Type) -> str:
        suffix = self.type_suffix(ty)
        table = {
            "==": f"CMP{suffix} ==",
            "!=": f"CMP{suffix} !=",
            "<": f"CMP{suffix} <",
            "<=": f"CMP{suffix} <=",
            ">": f"CMP{suffix} >",
            ">=": f"CMP{suffix} >=",
        }
        if oper not in table:
            raise NotImplementedError(f"Comparación no soportada: {oper}")
        return table[oper]

    def binary_bit_opcode(self, oper: str, ty: Type) -> str:
        table = {
            "&": "AND",
            "|": "OR",
            "^": "XOR",
        }
        if oper not in table:
            raise NotImplementedError(f"Bitwise no soportado: {oper}")
        return table[oper]

    # -------------------------------------------------
    # programa y declaraciones
    # -------------------------------------------------

    def visit_Program(self, node):
        self.push_scope()

        # Primera pasada: registrar nombres globales.
        for decl in node.decls:
            if isinstance(decl, (DeclTyped, DeclInit)):
                # Si es una función (DeclInit con typ=FuncType), registrarla apropiadamente
                if isinstance(decl.typ, FuncType):
                    self.bind(Storage(decl.name, decl.typ, is_global=True))
                else:
                    self.bind(
                        Storage(
                            decl.name,
                            decl.typ,
                            is_global=True,
                            is_const=isinstance(decl, DeclInit) and hasattr(decl, 'is_const'),
                        )
                    )
            elif hasattr(decl, 'type') and isinstance(decl.type, FuncType):
                self.bind(Storage(decl.name, decl.type, is_global=True))

        # Segunda pasada: generar IR real.
        for decl in node.decls:
            self.visit(decl)

        self.pop_scope()
        return self.program

    def visit_DeclTyped(self, node):
        if isinstance(node.typ, ArrayType):
            return #eliminamos la declaracion de esa vaina porque lo imprime sin necesidad (arr)
        elif self.current_function is None:
            self.emit(self.var_opcode(node.typ), node.name)
            print(node.name, node.typ)
            return
        
        self.bind(Storage(node.name, node.typ, is_const=False))
        self.emit(self.alloc_opcode(node.typ), node.name)

    def visit_DeclInit(self, node):
        # Si es una función, procesarla como tal
        if isinstance(node.typ, FuncType):
            return self._visit_function(node)
        
        # Si no, procesarla como una variable con inicialización
        if self.current_function is None:
            self.emit(self.var_opcode(node.typ), node.name)
            src = self.visit(node.init)
            self.emit(self.store_opcode(node.typ), src, node.name)
            return

        self.bind(Storage(node.name, node.typ, is_const=False))
        self.emit(self.alloc_opcode(node.typ), node.name)
        src = self.visit(node.init)
        self.emit(self.store_opcode(node.typ), src, node.name)

    def _visit_function(self, node):
        """Procesa una declaración de función (como DeclInit con typ=FuncType)."""
        prev_fn = self.current_function
        prev_ret = self.current_return_type

        fn = IRFunction(
            name=node.name,
            params=[(p.name, p.typ) for p in node.typ.params],
            return_type=node.typ.ret,
        )
        self.program.functions.append(fn)
        self.current_function = fn
        self.current_return_type = node.typ.ret

        self.push_scope()
        for p in node.typ.params:
            self.bind(Storage(p.name, p.typ, is_param=True))
            self.emit(self.alloc_opcode(p.typ), p.name)

        self.visit(node.init)  # node.init es el Block del cuerpo

        # Soporte mínimo para funciones void.
        if isinstance(node.typ.ret, VoidType) or (hasattr(node.typ.ret, 'name') and node.typ.ret.name == 'void'):
            if not fn.instructions or fn.instructions[-1][0] != "RET":
                self.emit("RET")

        self.pop_scope()
        self.current_function = prev_fn
        self.current_return_type = prev_ret

    def visit_FuncDecl(self, node):
        """Visita una declaración de función (FuncDecl)."""
        prev_fn = self.current_function
        prev_ret = self.current_return_type

        fn = IRFunction(
            name=node.name,
            params=[(p.name, p.typ) for p in node.params],
            return_type=node.typ,
        )
        self.program.functions.append(fn)
        self.current_function = fn
        self.current_return_type = node.typ

        self.push_scope()
        for p in node.params:
            self.bind(Storage(p.name, p.typ, is_param=True))
            self.emit(self.alloc_opcode(p.typ), p.name)

        self.visit(node.body)

        # Soporte mínimo para funciones void.
        if isinstance(node.typ, VoidType):
            if not fn.instructions or fn.instructions[-1][0] != "RET":
                self.emit("RET")

        self.pop_scope()
        self.current_function = prev_fn
        self.current_return_type = prev_ret

    def visit_Block(self, node):
        self.push_scope()
        for stmt in node.stmts:
            self.visit(stmt)
        self.pop_scope()

    def visit_Param(self, node):
        return None

    # -------------------------------------------------
    # statements
    # -------------------------------------------------

    def visit_Assign(self, node):
        """
        Implementación parcial.

        Ya resuelto:
        - asignación simple a variables: x = expr
        - asignación a Index (arreglos)
        """
        if isinstance(node.target, Name):
            storage = self.lookup(node.target.id)
            src = self.visit(node.value)
            self.emit(self.store_opcode(storage.ty), src, storage.name)

        elif isinstance(node.target, Index):
            # Obtener nombre del array
            array_name = node.target.base.id
            
            # Crear label global para el array si no existe
            if array_name not in self.array_tabla:
                array_label = f"ARR{self.array_count}"
                self.array_tabla[array_name] = array_label
                self.array_count += 1
                # Guardar en globals
                self.program.globals.append((f".{array_label}", []))
            else:
                array_label = self.array_tabla[array_name]

            #cargamos el array en un nuevo R
            array_addr = self.new_temp()
            self.emit("ADDAR", f".{array_label}", array_addr)

            #sacamos los indices
            index_regs = []
            for index_expr in node.target.indices:
                index_reg = self.visit(index_expr)
                index_regs.append(index_reg)

            #sacamos el valor a asignar
            value_reg = self.visit(node.value)

            #si hay index sacamos el valor de donde vamos a escribir, si no hay pues lo escribimos al inicio
            offset = index_regs[0] if index_regs else 0
            
            #guardamos el valor en la direccion del array STOREAR array direccion y valor a asignar
            self.emit("STOREAR", array_addr, offset, value_reg)
            
    def visit_Print(self, node):
        for expr in node.values:
            reg = self.visit(expr)
            ty = self.infer_type(expr)
            self.emit(self.print_opcode(ty), reg)

    def visit_If(self, node):
        label_else = self.new_label()
        label_end = self.new_label()

        cond = self.visit(node.cond)

        self.emit("CBRANCH", cond, label_else)

        #if verdadero
        self.visit(node.then)
        self.emit("BRANCH", label_end)

        #if falso (else)
        self.emit("LABEL", label_else)
        if node.otherwise: self.visit(node.otherwise) #(porque como es opcional se debe verificar)

        #salida del if
        self.emit("LABEL", label_end)

    def visit_While(self, node):
        label_start = self.new_label()
        label_end = self.new_label()

        self.loop_actual = (label_end, label_start, label_start)#label start sale en las 2 para el continue, porque pues no tiene steps

        #inicio del ciclo
        self.emit("LABEL", label_start)
        cond = self.visit(node.cond)
        self.emit("CBRANCH", cond, label_end)

        #hace lo que sea que tenga el cuerp y luego lo devuelve al inicio
        self.visit(node.body)
        self.emit("BRANCH", label_start)

        #si desde el inicio o al volver al inicio la condicion ya no se cumple pues se devuelve al label_end y se sale del ciclo
        self.emit("LABEL", label_end)

        self.loop_actual = None

    def visit_For(self, node):
        if node.init: self.visit(node.init) #si tiene init lo ejecuta para guardar la variable

        label_start = self.new_label()
        label_end = self.new_label()
        label_step = self.new_label() #para usar el continue ya que con flujo normar no es necesario

        self.loop_actual = (label_end, label_start, label_step)

        self.emit("LABEL", label_start)
        if node.cond: #si tiene condicion la evalua y si no pues es un for infinito
            cond = self.visit(node.cond)
            self.emit("CBRANCH", cond, label_end)

        #cosas del for
        self.visit(node.body)

        self.emit("LABEL", label_step) #Continue

        #el incremento
        self.visit(node.step)
        self.emit("BRANCH", label_start)

        #deonde se sale
        self.emit("LABEL", label_end)

        self.loop_actual = None

    def visit_Return(self, node):
        if node.value is None:
            self.emit("RET")
            return

        reg = self.visit(node.value)
        self.emit("RET", reg)

    # -------------------------------------------------
    # expressions
    # -------------------------------------------------

    def visit_Name(self, node):
        storage = self.lookup(node.id)
        tmp = self.new_temp()
        self.emit(self.load_opcode(storage.ty), storage.name, tmp)
        return tmp

    def visit_Index(self, node):
        # Obtener nombre del array
        array_name = node.base.id
        
        # Crear label global para el array si no existe
        if array_name not in self.array_tabla:
            array_label = f"ARR{self.array_count}"
            self.array_tabla[array_name] = array_label
            self.array_count += 1

            #guardar en global como un array
            self.program.globals.append((f".{array_label}", []))
        else:
            array_label = self.array_tabla[array_name]
        
        #llama la direccion del array
        array_addr = self.new_temp()
        self.emit("ADDAR", f".{array_label}", array_addr)
        
        #miramos los index del array
        index_regs = []
        for index_expr in node.indices:
            index_reg = self.visit(index_expr)
            index_regs.append(index_reg)
        
        offset = index_regs[0] if index_regs else 0
        
        out = self.new_temp()
        
        #sacamos el valor en la direccion del array LOAD array direccion y valor a asignar
        self.emit(f"LOADAR", array_addr, offset, out)
        
        return out

    def visit_BinOp(self, node):
        """
        Implementación al 50%.

        Ya resuelto:
        - esqueleto general
        - aritmética básica + - * /
        - comparaciones == != < <= > >= (:DDDDDDDDDD)
        - operaciones bit a bit se supone (no? solo es conectarlo con lo que ya habia)
        - booleanos lógicos (&& y ||) (la ia si le sabia, yo soy el idiota que no vio que eso ya estaba definido mas arriba)
        - cortocircuito real para && y ||
        - strings
        """
        left_reg = self.visit(node.left)
        right_reg = self.visit(node.right)
        left_ty = self.infer_type(node.left)
        right_ty = self.infer_type(node.right)
        out = self.new_temp()

        if node.op in {"+", "-", "*", "/"}:
            opcode = self.binary_arith_opcode(node.op, left_ty)
            self.emit(opcode, left_reg, right_reg, out)
            return out

        if node.op in {"==", "!=", "<", "<=", ">", ">="}:
            opcode = self.binary_cmp_opcode(node.op, left_ty)
            self.emit(opcode, left_reg, right_reg, out)
            return out
        
        if node.op in {"&", "|", "^"}:
            opcode = self.binary_bit_opcode(node.op, left_ty)
            self.emit(opcode, left_reg, right_reg, out)
            return out
        
        if node.op in {"&&", "||"}:
            left_bool = self.new_temp()
            right_bool = self.new_temp()
            label_end = self.new_label()
            do_right = self.new_label()

            if node.op == "&&":
                self.emit("CMPI !=", left_reg, 0, left_bool)
                self.emit("MOVI", left_bool, out)#movi en caso de que el resultado de la parte izquierda sea 0 out temporal

                #si lef_bool es 0 entonces saltamos a label_end para hacer el cortocircuito
                self.emit("CBRANCH", left_bool, label_end)

                self.emit("CMPI !=", right_reg, 0, right_bool)
                self.emit("AND", left_bool, right_bool, out) #ya aca si ncomparacion normal y se escribe el out final

                self.emit("LABEL", label_end)

            elif node.op == "||":
                self.emit("CMPI !=", left_reg, 0, left_bool)
                self.emit("MOVI", left_bool, out)

                #si left bool es 0 entonces revisamos el otro, si no entonces saltamos al final porque si es 1 entonces ya es true todo
                self.emit("CBRANCH", left_bool, do_right)
                self.emit("BRANCH", label_end)

                self.emit("LABEL", do_right)
                self.emit("CMPI !=", right_reg, 0, right_bool)
                self.emit("OR", left_bool, right_bool, out) #verifica todo (innecesario segun chayi pero asi se entiende mas facil)

                self.emit("LABEL", label_end)

            return out

    def visit_UnaryOp(self, node):
        expr_reg = self.visit(node.expr)
        expr_ty = self.infer_type(node.expr)
        out = self.new_temp()

        if node.op == "+":
            self.emit(f"MOV{self.type_suffix(expr_ty)}", expr_reg, out)
            return out
        if node.op == "-":
            zero = self.new_temp()
            self.emit(f"MOV{self.type_suffix(expr_ty)}", 0, zero)
            self.emit(f"SUB{self.type_suffix(expr_ty)}", zero, expr_reg, out)
            return out
        if node.op == "!":
            self.emit(f"NOT{self.type_suffix(expr_ty)}", expr_reg, out)
            return out

        raise NotImplementedError(
            "UnaryOp (+, -, !) (esto deberia de estar completamente resuelto, si sale esto estamos jodidos)"
        )

    def visit_Literal(self, node):
        tmp = self.new_temp()
        if node.kind == "integer":
            self.emit("MOVI", int(node.value), tmp)
        elif node.kind == "boolean":
            self.emit("MOVI", 1 if node.value else 0, tmp)
        elif node.kind == "char":
            value = ord(node.value) if isinstance(node.value, str) else int(node.value)
            self.emit("MOVB", value, tmp)

        elif node.kind == "string":
            if node.value not in self.string_tabla:
                #si no existe en la tabla significa que no hay lebel entonces lo creamos
                string_lable = f"STR{self.string_count}"
                self.string_tabla[node.value] = string_lable

                #saca los caracterres y los guarda en global
                string_chars = []
                for char in node.value:
                    string_chars.append(ord(char)) #codigo ascii pa
                string_chars.append(0) #agrega el caracter nulo al final

                #crea la etiqueta para guardar el string
                self.program.globals.append((f".{string_lable}", string_chars))
                self.string_count += 1


            #si ya existia o si lo acaba de crear viene aqui y llama al label
            string_lable = self.string_tabla[node.value]
            self.emit("ADDR", f".{string_lable}", tmp)

            
        else:
            raise NotImplementedError(f"Literal tipo {node.kind} no soportado")
        return tmp

    def visit_ExprStmt(self, node):
        """Visita un statement de expresión."""
        self.visit(node.expr)

    def visit_Break(self, node):
        """Visita un statement break."""
        self.emit("BRANCH", self.loop_actual[0])#si es breake llama directamente a label_end

    def visit_Continue(self, node):
        """Visita un statement continue."""
        self.emit("BRANCH", self.loop_actual[2])#si es continue llama a label_step

    def visit_Call(self, node):
        """Visita una llamada a función simple."""
        arg_regs = []
        for arg in getattr(node, 'args', []):
            arg_reg = self.visit(arg)
            arg_regs.append(arg_reg)

        out = self.new_temp()
        self.emit("CALL", node.func, *arg_regs, out)
        return out

    def visit_TernOp(self, node):
        label_else = self.new_label()
        label_end = self.new_label()
        out = self.new_temp()
        
        cond = self.visit(node.cond)
        self.emit("CBRANCH", cond, label_else)
        
        #true
        true_val = self.visit(node.then)
        
        true_ty = self.infer_type(node.then)
        self.emit(self.move_opcode(true_ty), true_val, out)
        self.emit("BRANCH", label_end)
        
        #false
        self.emit("LABEL", label_else)
        false_val = self.visit(node.otherwise)
        false_ty = self.infer_type(node.otherwise)
        self.emit(self.move_opcode(false_ty), false_val, out)
        
        self.emit("LABEL", label_end)
        return out

    def visit_PostfixOp(self, node):
        """Visita un operador de postfijo."""
        if not isinstance(node.expr, Name): raise NotImplementedError("esto no deberia estar pasando porque el semantico lo hace")

        variable = self.lookup(node.expr.id)

        old_var = self.new_temp()
        self.emit(self.load_opcode(variable.ty), variable.name, old_var)

        out = self.new_temp()
        if node.op== "++":
            self.emit("ADDI", old_var, 1, out)
        elif node.op == "--":
            self.emit("SUBI", old_var, 1, out)
        else:
            raise NotImplementedError(f"Operador de postfijo no soportado: {node.op} (no deberia de aparecer porque el semantico ya lo verifica)")

        self.emit(self.store_opcode(variable.ty), out, variable.name)

        return out

    #clases y metodos y todo eso

    def visit_ClassDecl(self, node):
        """
        Visita una declaración de clase.
        
        Una clase es esencialmente un contenedor de miembros (variables y métodos).
        En el IR, emitimos:
        1. Etiqueta de clase para referencia
        2. Procesamos cada miembro del cuerpo
        """
        # Emitir una etiqueta de inicio de clase
        self.emit(f"CLASS {node.name}")
        
        # Procesar el cuerpo de la clase si existe
        if node.body:
            self.push_scope()
            for member in node.body:
                self.visit(member)
            self.pop_scope()
        
        # Etiqueta de fin de clase
        self.emit(f"END_CLASS {node.name}")

    def visit_MemberCall(self, node):
        """Visita una llamada a método/miembro."""
        self.visit(node.target)

        target_name = node.target.id if isinstance(node.target, Name) else "expr"

        for member in node.members:
            if isinstance(member, Name):
                target_name = f"{target_name}.{member.id}"
                continue

            if isinstance(member, Index):
                index_regs = [self.visit(idx) for idx in member.indices]
                target_name = f"{target_name}[{','.join(str(r) for r in index_regs)}]"
                continue

            if isinstance(member, Call):
                arg_regs = [self.visit(arg) for arg in getattr(member, 'args', []) or []]
                out = self.new_temp()
                self.emit("CALL", f"{target_name}.{member.func}", *arg_regs, out)
                return out

            raise NotImplementedError("MemberCall member type no soportado")

        # Si no hay un Call dentro de la cadena de miembros, devolvemos el valor del target.
        return self.visit(node.target)

    def visit_Constructor(self, node):
        """
        Visita un constructor (expresión NEW).
        
        Sintaxis: NEW ClassName(arg1, arg2, ...)
        
        En el IR, emitimos:
        1. Evaluamos cada argumento
        2. Emitimos una instrucción NEW con el tipo de clase y argumentos
        3. Retornamos un temporal con la referencia a la nueva instancia
        """
        # Evaluar todos los argumentos del constructor
        arg_regs = []
        for arg in node.atts:
            arg_reg = self.visit(arg)
            arg_regs.append(arg_reg)
        
        # Crear un temporal para guardar la instancia
        out = self.new_temp()
        
        # Emitir instrucción NEW
        self.emit("NEW", node.type, *arg_regs, out)
        
        return out


# ===================================================
# demo
# ===================================================

if __name__ == "__main__":
    import sys

    if "-ir" in sys.argv:
        filename = sys.argv[1]
        with open(filename, encoding="utf-8") as f:
            txt = f.read()
            check = semantic_check(txt) #.ok(), lista de errores, ast

            if check[0]: sys.exit(1) #si hubieron errores semanticos pues no ejecuta ni mierda

            ir = IRCodeGen.generate()
            print(ir.format())

    else:
        print("Demo de IRCodeGen con ejemplos simples si desea ejecutar codigo txt usar -ir:\n")
        # msg: string = "Hola mundo";
        # print(msg);
        ast = Program([
            DeclInit(
                name="main",
                typ=FuncType(ret=VOID, params=[]),
                init=Block(stmts=[
                    DeclInit(
                        name="msg",
                        typ=STRING,
                        init=Literal(kind="string", value="Hola mundo"),
                    ),
                    Print(values=[Name(id="msg")]),
                ]),
            )
        ])
        ir = IRCodeGen.generate(ast)
        print(ir.format())
        
        print("\n" + "="*50 + "\n")
        
        # Prueba: print("hola") directamente
        ast2 = Program([
            DeclInit(
                name="main",
                typ=FuncType(ret=VOID, params=[]),
                init=Block(stmts=[
                    Print(values=[Literal(kind="string", value="Hola mundo")]),
                ]),
            )
        ])
        ir2 = IRCodeGen.generate(ast2)
        print(ir2.format())

        print("\n" + "="*50 + "\n")

        #prueba: x = (12 == 34)
        ast3 = Program([
            DeclInit(
                name="main",
                typ=FuncType(ret=VOID, params=[]),
                init=Block(stmts=[
                    DeclTyped(name="x", typ=BOOL),
                    Assign(
                        target=Name(id="x"),
                        value=BinOp(
                            left=Literal(kind="integer", value=12),
                            op="==",
                            right=Literal(kind="integer", value=34),
                        )
                    ),
                ]),
            )
        ])
        ir3 = IRCodeGen.generate(ast3)
        print(ir3.format())

        print("\n" + "="*50 + "\n")

        # Prueba: operaciones bitwise
        # z = (5 & 3) | (2 ^ 1)
        ast4 = Program([
            DeclInit(
                name="main",
                typ=FuncType(ret=VOID, params=[]),
                init=Block(stmts=[
                    DeclInit(
                        name="z",
                        typ=INT,
                        init=BinOp(
                            left=BinOp(
                                left=Literal(kind="integer", value=5),
                                op="&",
                                right=Literal(kind="integer", value=3),
                            ),
                            op="|",
                            right=BinOp(
                                left=Literal(kind="integer", value=2),
                                op="^",
                                right=Literal(kind="integer", value=1),
                            ),
                        ),
                    ),
                    Print(values=[Name(id="z")]),
                ]),
            )
        ])
        ir4 = IRCodeGen.generate(ast4)
        print(ir4.format())

        print("\n" + "="*50 + "\n")

        # Prueba: operaciones unarias
        # a = -10; b = !true; c = +5
        ast5 = Program([
            DeclInit(
                name="main",
                typ=FuncType(ret=VOID, params=[]),
                init=Block(stmts=[
                    DeclInit(
                        name="a",
                        typ=INT,
                        init=UnaryOp(op="-", expr=Literal(kind="integer", value=10)),
                    ),
                    DeclInit(
                        name="b",
                        typ=BOOL,
                        init=UnaryOp(op="!", expr=Literal(kind="boolean", value=True)),
                    ),
                    DeclInit(
                        name="c",
                        typ=INT,
                        init=UnaryOp(op="+", expr=Literal(kind="integer", value=5)),
                    ),
                    Print(values=[Name(id="a"), Name(id="b"), Name(id="c")]),
                ]),
            )
        ])
        ir5 = IRCodeGen.generate(ast5)
        print(ir5.format())

        print("\n" + "="*50 + "\n")

        # Prueba: comparaciones con >=
        # x: integer = 10; y: integer = 5;
        # result = x >= y
        ast6 = Program([
            DeclInit(
                name="x",
                typ=INT,
                init=Literal(kind="integer", value=10),
            ),
            DeclInit(
                name="y",
                typ=INT,
                init=Literal(kind="integer", value=5),
            ),
            DeclInit(
                name="main",
                typ=FuncType(ret=VOID, params=[]),
                init=Block(stmts=[
                    DeclInit(
                        name="result",
                        typ=BOOL,
                        init=BinOp(
                            left=Name(id="x"),
                            op=">=",
                            right=Name(id="y"),
                        ),
                    ),
                    Print(values=[Name(id="result")]),
                ]),
            )
        ])
        ir6 = IRCodeGen.generate(ast6)
        print(ir6.format())

        print("\n" + "="*50 + "\n")

        # Prueba: postfijos
        ast7 = Program([
            DeclInit(
                name="main",
                typ=FuncType(ret=VOID, params=[]),
                init=Block(stmts=[
                    DeclInit(
                        name="x",
                        typ=INT,
                        init=Literal(kind="integer", value=1),
                    ),
                    DeclInit(
                        name="y",
                        typ=INT,
                        init=Literal(kind="integer", value=2),
                    ),
                    ExprStmt(
                        expr=PostfixOp(
                            expr=Name(id="x"),
                            op="++",
                        )
                    ),
                    ExprStmt(
                        expr=PostfixOp(
                            expr=Name(id="y"),
                            op="--",
                        )
                    ),
                    Print(values=[Name(id="x"), Name(id="y")]),
                ]),
            )
        ])
        ir7 = IRCodeGen.generate(ast7)
        print(ir7.format())

        print("\n" + "="*50 + "\n")

        # Prueba: if, while y for
        # if (x > 5) { print(1); } else { print(0); }
        # while (y < 10) { y++; }
        # for (i = 0; i < 3; i++) { print(i); }
        ast8 = Program([
            DeclInit(
                name="main",
                typ=FuncType(ret=VOID, params=[]),
                init=Block(stmts=[
                    DeclInit(
                        name="x",
                        typ=INT,
                        init=Literal(kind="integer", value=10),
                    ),
                    DeclInit(
                        name="y",
                        typ=INT,
                        init=Literal(kind="integer", value=0),
                    ),
                    # if (x > 5)
                    If(
                        cond=BinOp(
                            left=Name(id="x"),
                            op=">",
                            right=Literal(kind="integer", value=5),
                        ),
                        then=Block(stmts=[
                            Print(values=[Literal(kind="integer", value=1)]),
                        ]),
                        otherwise=Block(stmts=[
                            Print(values=[Literal(kind="integer", value=0)]),
                        ]),
                    ),
                    # while (y < 10) { y++; }
                    While(
                        cond=BinOp(
                            left=Name(id="y"),
                            op="<",
                            right=Literal(kind="integer", value=10),
                        ),
                        body=Block(stmts=[
                            ExprStmt(
                                expr=PostfixOp(
                                    expr=Name(id="y"),
                                    op="++",
                                )
                            ),
                        ]),
                    ),
                    # for (i = 0; i < 3; i++) { print(i); }
                    For(
                        init=Assign(
                            target=Name(id="x"),
                            value=Literal(kind="integer", value=0),
                        ),
                        cond=BinOp(
                            left=Name(id="x"),
                            op="<",
                            right=Literal(kind="integer", value=3),
                        ),
                        step=ExprStmt(
                            expr=PostfixOp(
                                expr=Name(id="x"),
                                op="++",
                            )
                        ),
                        body=Block(stmts=[
                            Print(values=[Name(id="x")]),
                        ]),
                    ),
                ]),
            )
        ])
        ir8 = IRCodeGen.generate(ast8)
        print(ir8.format())

        print("\n" + "="*50 + "\n")

        # Prueba: arrays bidimensionales
        # Simula: matriz[2][3]
        # matriz[0][0] = 1
        # matriz[1][2] = 5
        # x = matriz[0][0]
        # y = matriz[1][2]
        ast9 = Program([
            DeclTyped(
                name="matriz",
                typ=INT,
            ),
            DeclInit(
                name="main",
                typ=FuncType(ret=VOID, params=[]),
                init=Block(stmts=[
                    # matriz[0][0] = 1
                    Assign(
                        target=Index(
                            base=Name(id="matriz"),
                            indices=[
                                Literal(kind="integer", value=0),
                                Literal(kind="integer", value=0),
                            ],
                        ),
                        value=Literal(kind="integer", value=1),
                    ),
                    # matriz[1][2] = 5
                    Assign(
                        target=Index(
                            base=Name(id="matriz"),
                            indices=[
                                Literal(kind="integer", value=1),
                                Literal(kind="integer", value=2),
                            ],
                        ),
                        value=Literal(kind="integer", value=5),
                    ),
                    # x = matriz[0][0]
                    DeclInit(
                        name="x",
                        typ=INT,
                        init=Index(
                            base=Name(id="matriz"),
                            indices=[
                                Literal(kind="integer", value=0),
                                Literal(kind="integer", value=0),
                            ],
                        ),
                    ),
                    # y = matriz[1][2]
                    DeclInit(
                        name="y",
                        typ=INT,
                        init=Index(
                            base=Name(id="matriz"),
                            indices=[
                                Literal(kind="integer", value=1),
                                Literal(kind="integer", value=2),
                            ],
                        ),
                    ),
                    # print(x, y)
                    Print(values=[Name(id="x"), Name(id="y")]),
                ]),
            )
        ])
        ir9 = IRCodeGen.generate(ast9)
        print(ir9.format())

        print("\n" + "="*50 + "\n")

        ast10 = Program([
            DeclInit(
                name="main",
                typ=FuncType(ret=VOID, params=[]),
                init=Block(stmts=[
                    DeclTyped(name="i", typ=SimpleType("integer")),
                    For(
                        init=Assign(
                            target=Name(id="i"),
                            value=Literal(kind="integer", value=0),
                        ),
                        cond=BinOp(
                            left=Name(id="i"),
                            op="<",
                            right=Literal(kind="integer", value=10),
                        ),
                        step=Assign(
                            target=Name(id="i"),
                            value=BinOp(
                                left=Name(id="i"),
                                op="+",
                                right=Literal(kind="integer", value=1),
                            ),
                        ),
                        body=Block(stmts=[
                            If(
                                cond=BinOp(
                                    left=Name(id="i"),
                                    op="==",
                                    right=Literal(kind="integer", value=5),
                                ),
                                then=Continue(),
                            ),
                            If(
                                cond=BinOp(
                                    left=Name(id="i"),
                                    op="==",
                                    right=Literal(kind="integer", value=8),
                                ),
                                then=Break(),
                            ),
                            Print(values=[Name(id="i")]),
                        ]),
                    ),
                ]),
            )
        ])
        ir10 = IRCodeGen.generate(ast10)
        print(ir10.format())

        print("\n" + "="*50 + "\n")

        # Prueba: llamadas Call y MemberCall
        ast11 = Program([
            DeclInit(
                name="foo",
                typ=FuncType(ret=INT, params=[
                    Param(name="a", typ=INT),
                    Param(name="b", typ=INT),
                ]),
                init=Block(stmts=[
                    Return(
                        value=BinOp(
                            left=Name(id="a"),
                            op="+",
                            right=Name(id="b"),
                        )
                    ),
                ]),
            ),
            DeclInit(
                name="bar",
                typ=FuncType(ret=INT, params=[Param(name="x", typ=INT)]),
                init=Block(stmts=[
                    Return(
                        value=BinOp(
                            left=Name(id="x"),
                            op="*",
                            right=Literal(kind="integer", value=2),
                        )
                    ),
                ]),
            ),
            DeclInit(
                name="main",
                typ=FuncType(ret=VOID, params=[]),
                init=Block(stmts=[
                    DeclInit(
                        name="sum",
                        typ=INT,
                        init=Call(
                            func="foo",
                            args=[
                                Literal(kind="integer", value=3),
                                Literal(kind="integer", value=4),
                            ],
                        ),
                    ),
                    DeclInit(
                        name="obj",
                        typ=INT,
                        init=Literal(kind="integer", value=0),
                    ),
                    DeclInit(
                        name="result",
                        typ=INT,
                        init=MemberCall(
                            target=Name(id="obj"),
                            members=[
                                Call(
                                    func="bar",
                                    args=[Literal(kind="integer", value=5)],
                                ),
                            ],
                        ),
                    ),
                    Print(values=[Name(id="sum"), Name(id="result")]),
                ]),
            ),
        ])
        ir11 = IRCodeGen.generate(ast11)
        print(ir11.format())

        print("\n" + "="*50 + "\n")

        # Prueba: clases, constructores y member calls
        # Definición simple de clase Point
        ast12 = Program([
            ClassDecl(
                name="Point",
                body=[
                    DeclTyped(name="x", typ=INT),
                    DeclTyped(name="y", typ=INT),
                ],
            ),
            DeclInit(
                name="main",
                typ=FuncType(ret=VOID, params=[]),
                init=Block(stmts=[
                    # Crear instancia de Point usando constructor
                    DeclInit(
                        name="p",
                        typ=SimpleType("Point"),
                        init=Constructor(
                            type="Point",
                            atts=[
                                Literal(kind="integer", value=10),
                                Literal(kind="integer", value=20),
                            ],
                        ),
                    ),
                    # Simular acceso a miembros usando MemberCall
                    DeclInit(
                        name="px",
                        typ=INT,
                        init=MemberCall(
                            target=Name(id="p"),
                            members=[
                                Name(id="x"),
                            ],
                        ),
                    ),
                    DeclInit(
                        name="py",
                        typ=INT,
                        init=MemberCall(
                            target=Name(id="p"),
                            members=[
                                Name(id="y"),
                            ],
                        ),
                    ),
                    # Imprimir resultados
                    Print(values=[Name(id="px"), Name(id="py")]),
                ]),
            ),
        ])
        ir12 = IRCodeGen.generate(ast12)
        print(ir12.format())

        print("\n" + "="*50 + "\n")

        # Prueba: Arrays con definición e inicialización
        # arr: integer[] = ...
        # arr[0] = 1; arr[1] = 2; arr[2] = 3; arr[3] = 5
        # print(arr[0], arr[1], arr[2], arr[3])
        ast13 = Program([
            DeclTyped(
                name="arr",
                typ=ArrayType(elem=INT),
            ),
            DeclInit(
                name="main",
                typ=FuncType(ret=VOID, params=[]),
                init=Block(stmts=[
                    # Asignaciones a índices específicos
                    Assign(
                        target=Index(
                            base=Name(id="arr"),
                            indices=[Literal(kind="integer", value=0)],
                        ),
                        value=Literal(kind="integer", value=1),
                    ),
                    Assign(
                        target=Index(
                            base=Name(id="arr"),
                            indices=[Literal(kind="integer", value=1)],
                        ),
                        value=Literal(kind="integer", value=2),
                    ),
                    Assign(
                        target=Index(
                            base=Name(id="arr"),
                            indices=[Literal(kind="integer", value=2)],
                        ),
                        value=Literal(kind="integer", value=3),
                    ),
                    Assign(
                        target=Index(
                            base=Name(id="arr"),
                            indices=[Literal(kind="integer", value=3)],
                        ),
                        value=Literal(kind="integer", value=5),
                    ),
                    # Lectura y impresión de índices
                    Print(values=[
                        Index(
                            base=Name(id="arr"),
                            indices=[Literal(kind="integer", value=0)],
                        ),
                        Index(
                            base=Name(id="arr"),
                            indices=[Literal(kind="integer", value=1)],
                        ),
                        Index(
                            base=Name(id="arr"),
                            indices=[Literal(kind="integer", value=2)],
                        ),
                        Index(
                            base=Name(id="arr"),
                            indices=[Literal(kind="integer", value=3)],
                        ),
                    ]),
                ]),
            ),
        ])
        ir13 = IRCodeGen.generate(ast13)
        print(ir13.format())