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
        if self.current_function is None:
            self.emit(self.var_opcode(node.typ), node.name)
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

        Ejercicio para estudiantes:
        - asignación a Index (arreglos)
        - impedir escritura en constantes (si desean reforzarlo aquí)
        """
        if not isinstance(node.target, Name):
            raise NotImplementedError(
                "Starter: Assign solo soporta Name (variables simples) por ahora"
            )

        storage = self.lookup(node.target.id)
        src = self.visit(node.value)
        self.emit(self.store_opcode(storage.ty), src, storage.name)

    def visit_Print(self, node):
        for expr in node.values:
            reg = self.visit(expr)
            ty = self.infer_type(expr)
            self.emit(self.print_opcode(ty), reg)

    def visit_If(self, node):
        raise NotImplementedError(
            "TODO estudiante: generar labels y branches para If"
        )

    def visit_While(self, node):
        raise NotImplementedError(
            "TODO estudiante: generar labels y branches para While"
        )

    def visit_For(self, node):
        raise NotImplementedError(
            "TODO estudiante: generar labels y branches para For"
        )

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
        raise NotImplementedError(
            "TODO estudiante: implementar acceso a arreglos (Index)"
        )

    def visit_Call(self, node):
        raise NotImplementedError(
            "TODO estudiante: implementar evaluación de argumentos y CALL"
        )

    def visit_BinOp(self, node):
        """
        Implementación al 50%.

        Ya resuelto:
        - esqueleto general
        - aritmética básica + - * /
        - comparaciones == != < <= > >= (:DDDDDDDDDD)
        - operaciones bit a bit se supone (no? solo es conectarlo con lo que ya habia)
        - booleanos lógicos (&& y ||) (la ia si le sabia, yo soy el idiota que no vio que eso ya estaba definido mas arriba)

        Pendiente:
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
            opcode = "AND" if node.op == "&&" else "OR"

            left_bool = self.new_temp()
            right_bool = self.new_temp()

            #guarda el resultaddo de cada uno de los lados de la operacion en un registro aparte
            self.emit("CMPI !=", left_reg, 0, left_bool)
            self.emit("CMPI !=", right_reg, 0, right_bool)

            #y ahora compara esas 2 vainas para guardar en otro registro el resultado de las 2 cosas
            self.emit(opcode, left_bool, right_bool, out)
            return out



        raise NotImplementedError(
            f"TODO estudiante: completar BinOp para operador {node.op!r} (aun faltan booleanos lógicos y cortocircuito)"
        )

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
            "TODO estudiante: implementar UnaryOp (+, -, !) (esto deberia de estar completamente resuelto, si sale esto estamos jodidos)"
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
            raise NotImplementedError(f"Literal tipo {node.kind} no soportado u")
        else:
            raise NotImplementedError(f"Literal tipo {node.kind} no soportado")
        return tmp

    def visit_ExprStmt(self, node):
        """Visita un statement de expresión."""
        self.visit(node.expr)

    def visit_Break(self, node):
        """Visita un statement break."""
        raise NotImplementedError("TODO estudiante: implementar break")

    def visit_Continue(self, node):
        """Visita un statement continue."""
        raise NotImplementedError("TODO estudiante: implementar continue")

    def visit_ClassDecl(self, node):
        """Visita una declaración de clase."""
        raise NotImplementedError("TODO estudiante: implementar clases")

    def visit_TernOp(self, node):
        """Visita un operador ternario."""
        raise NotImplementedError("TODO estudiante: implementar operador ternario")

    def visit_MemberCall(self, node):
        """Visita una llamada a miembro."""
        raise NotImplementedError("TODO estudiante: implementar llamadas a miembros")

    def visit_PostfixOp(self, node):
        """Visita un operador de postfijo."""
        raise NotImplementedError("TODO estudiante: implementar operadores de postfijo")

    def visit_Constructor(self, node):
        """Visita un constructor."""
        raise NotImplementedError("TODO estudiante: implementar constructores")


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