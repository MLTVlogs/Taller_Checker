# astopt.py
# ---------------------------------------------------
# Optimizador O1 sobre AST para B-Minor
#
# Fase recomendada:
#
#     source
#       ↓
#     parser
#       ↓
#     checker
#       ↓
#     ASTOptimizer O1   ← este archivo
#       ↓
#     ircode
#
# ---------------------------------------------------

from __future__ import annotations

from dataclasses import replace, is_dataclass, fields
from typing import Optional
from checker import *
from rich import print

from model import *


# ---------------------------------------------------
# Utilidades para literales
# ---------------------------------------------------

def is_int(node):
    # return isinstance(node, Literal) and isinstance(node.value, int)
    return isinstance(node, Literal) and node.kind == "integer"
    
    
    
def is_float(node):
    # return isinstance(node, Literal) and isinstance(node.value, float)
    return isinstance(node, Literal) and node.kind == "float"
    
    
def is_bool(node):
    # return isinstance(node, Literal) and isinstance(node.value, bool)
    return isinstance(node, Literal) and node.kind == "boolean"
    
    
def is_char(node):
    return isinstance(node, Literal) and node.kind == "char"
    
    
def is_string(node):
    return isinstance(node, Literal) and node.kind == "string"
    
    
def is_number(node):
    return is_int(node) or is_float(node)
    
    
def value_of(node):
    return getattr(node, "value", None)
    
    
def is_zero(node):
    return is_number(node) and value_of(node) == 0
    
    
def is_one(node):
    return is_number(node) and value_of(node) == 1
    
    
def make_number(value, template):
    '''
    Crea un literal numérico conservando el tipo base 
    del template.
    '''
    if isinstance(template, Literal) and template.kind == "float":
        return Literal("float", float(value), lineno=getattr(template, "lineno", 0))
    return Literal("integer", int(value), lineno=getattr(template, "lineno", 0))
    
    
def make_bool(value, template=None):
    return Literal("boolean", bool(value), lineno=getattr(template, "lineno", 0) if template else 0)
    
    
def same_literal_family(a, b):
    """Familia compatible para folding directo."""
    if is_number(a) and is_number(b):
        return True
    return type(a) is type(b) and (
        is_bool(a) or is_char(a) or is_string(a)
    )
    
    
def has_side_effect(node):
    '''
    Conservador: una llamada puede tener efectos laterales.
    Se usa para evitar transformar x * 0 -> 0 si x es una llamada.
    '''
    if isinstance(node, Call) or isinstance(node, MemberCall): 
        return True
    if isinstance(node, BinOp):
        return has_side_effect(node.left) or has_side_effect(node.right)
    if isinstance(node, UnaryOp):
        return has_side_effect(node.expr)
    if isinstance(node, TernOp):
        return (
            has_side_effect(node.test)
            or has_side_effect(node.then_expr)
            or has_side_effect(node.else_expr)
        )
    return False
    
    
# ---------------------------------------------------
# Visitor de optimización O1
# ---------------------------------------------------

class ASTOptimizer(Visitor):
    def __init__(self):
        self.changed = False
        
    def mark_changed(self):
        self.changed = True
        
    # -------------------------------------------------
    # Fallback genérico
    # -------------------------------------------------
    
    def visit(self, node: Node):
        '''
        Fallback para nodos no especializados.
        Recorre dataclasses y optimiza campos que sean Node o list[Node].
        '''
        if not is_dataclass(node):
            return node
            
        updates = {}
        
        for f in fields(node):
            name = f.name
            value = getattr(node, name)
            
            if isinstance(value, list):
                new_list = []
                local_changed = False
                
                for item in value:
                    if isinstance(item, Node):
                        new_item = item.accept(self)
                        if new_item is None:
                            local_changed = True
                            self.mark_changed()
                            continue
                        if isinstance(new_item, list):
                            new_list.extend(new_item)
                            local_changed = True
                            self.mark_changed()
                        else:
                            new_list.append(new_item)
                            if new_item is not item:
                                local_changed = True
                    else:
                        new_list.append(item)
                        
                if local_changed:
                    updates[name] = new_list
                    
            elif isinstance(value, Node):
                new_value = value.accept(self)
                if new_value is not value:
                    updates[name] = new_value
                    
        if updates:
            self.mark_changed()
            return replace(node, **updates)
            
        return node
        
    # -------------------------------------------------
    # Programa y bloques
    # -------------------------------------------------
    
    def visit_Program(self, node):
        decls = []
        local_changed = False
        
        for decl in node.decls:
            new_decl = decl.accept(self)
            
            if new_decl is None:
                local_changed = True
                self.mark_changed()
                continue
                
            if isinstance(new_decl, list):
                decls.extend(new_decl)
                local_changed = True
                self.mark_changed()
            else:
                decls.append(new_decl)
                if new_decl is not decl:
                    local_changed = True
                    
        if local_changed:
            self.mark_changed()
            return replace(node, decls=decls)
            
        return node
        
    def visit_Block(self, node):
        stmts = []
        local_changed = False
        
        for stmt in node.stmts:
            new_stmt = stmt.accept(self)
            
            if new_stmt is None:
                local_changed = True
                self.mark_changed()
                continue
                
            # if true { ... } puede devolver un Block; se aplana.
            if isinstance(new_stmt, Block):
                stmts.extend(new_stmt.stmts)
                local_changed = True
                self.mark_changed()
                continue
                
            if isinstance(new_stmt, list):
                stmts.extend(new_stmt)
                local_changed = True
                self.mark_changed()
                continue
                
            stmts.append(new_stmt)
            if new_stmt is not stmt:
                local_changed = True
                
        if local_changed:
            self.mark_changed()
            return replace(node, stmts=stmts)
            
        return node
        
    # -------------------------------------------------
    # Declaraciones
    # -------------------------------------------------
    def visit_DeclTyped(self, node):
        return node
        
    def visit_DeclInit(self, node):
        # Si es una función, optimizarla como tal
        if isinstance(node.typ, FuncType):
            body = node.init.accept(self)
            if body is not node.init:
                self.mark_changed()
                return replace(node, init=body)
            return node
        elif isinstance(node.typ, ArraySizedType):
            # Si es un arreglo, optimizar la expresión de tamaño o inicialización
            updates = {}
            if getattr(node.typ, "size_expr", None) is not None and isinstance(node.typ.size_expr, Node):
                size = node.typ.size_expr.accept(self)
                if size is not node.typ.size_expr:
                    updates["size_expr"] = size
                
            value = getattr(node, "init", None)
            if value is not None and isinstance(value, Node):
                new_value = value.accept(self)
                if new_value is not value:
                    updates["init"] = new_value
                
            if updates:
                self.mark_changed()
                return replace(node, typ=replace(node.typ, **updates))
            return node
        elif isinstance(node.typ, SimpleType):
            if node.init is not None:
                return node
            value = node.init.accept(self)
            if value is not node.init:
                self.mark_changed()
                return replace(node, init=value)
            return node 
    
    def visit_ClassDecl(self, node):
        if node.body is None:
            return node
        decls = []
        local_changed = False
        for decl in node.body:
            new_decl = decl.accept(self)
            if new_decl is None:
                local_changed = True
                self.mark_changed()
                continue
            if isinstance(new_decl, list):
                decls.extend(new_decl)
                local_changed = True
                self.mark_changed()
            else:
                decls.append(new_decl)
                if new_decl is not decl:
                    local_changed = True
        if local_changed:
            self.mark_changed()
            return replace(node, body=decls)
        return node
    
    '''def visit_VarDecl(self, node: VarDecl):
        if node.value is None:
            return node
        value = node.value.accept(self)
        if value is not node.value:
            self.mark_changed()
            return replace(node, value=value)
        return node'''
        
    '''def visit(self, node: ConstDecl):
        value = node.value.accept(self)
        if value is not node.value:
            self.mark_changed()
            return replace(node, value=value)
        return node'''
        
    '''def visit(self, node: FuncDecl):
        body = node.body.accept(self)
        if body is not node.body:
            self.mark_changed()
            return replace(node, body=body)
        return node'''
        
    # Opcional: solo funcionará si agrega ArrayDecl a model.py.
    '''def visit(self, node: ArrayDecl):
        updates = {}
        
        if getattr(node, "size", None) is not None and isinstance(node.size, Node):
            size = node.size.accept(self)
            if size is not node.size:
                updates["size"] = size
                
        value = getattr(node, "value", None)
        if value is not None and isinstance(value, Node):
            new_value = value.accept(self)
            if new_value is not value:
                updates["value"] = new_value
                
        if updates:
            self.mark_changed()
            return replace(node, **updates)
            
        return node'''
        
    # -------------------------------------------------
    # Sentencias
    # -------------------------------------------------
    
    def visit_Assign(self, node):
        target = node.target.accept(self)
        value = node.value.accept(self)
        
        if target is not node.target or value is not node.value:
            self.mark_changed()
            return replace(node, target=target, value=value)
            
        return node
        
    def visit_Print(self, node):
        values = node.values.accept(self)
        if values is not node.values:
            self.mark_changed()
            return replace(node, values=values)
        return node
        
    def visit_Return(self, node):
        if node.value is None:
            return node
        value = node.value.accept(self)
        if value is not node.value:
            self.mark_changed()
            return replace(node, value=value)
        return node
        
    def visit_If(self, node):
        cond = node.cond.accept(self)
        then = node.then.accept(self)
        otherwise = node.otherwise.accept(self) if node.otherwise else None
        
        # if true { A } else { B } -> A
        # if false { A } else { B } -> B o eliminado
        if is_bool(cond):
            self.mark_changed()
            if cond.value:
                return then
            return otherwise
            
        if (
            cond is not node.cond
            or then is not node.then
            or otherwise is not node.otherwise
        ):
            self.mark_changed()
            return replace(
                node,
                cond=cond,
                then=then,
                otherwise=otherwise,
            )
            
        return node
        
    def visit_While(self, node):
        cond = node.cond.accept(self)
        body = node.body.accept(self)
        
        # while false { ... } -> eliminado
        if is_bool(cond) and cond.value is False:
            self.mark_changed()
            return None
            
        if cond is not node.cond or body is not node.body:
            self.mark_changed()
            return replace(node, cond=cond, body=body)
            
        return node
        
    def visit_For(self, node):
        init = node.init.accept(self) if node.init else None
        cond = node.cond.accept(self) if node.cond else None
        step = node.step.accept(self) if node.step else None
        body = node.body.accept(self)
        
        # for(init; false; step) body -> init
        if cond is not None and is_bool(cond) and cond.value is False:
            self.mark_changed()
            return init
            
        if init is not node.init or cond is not node.cond or step is not node.step or body is not node.body:
            self.mark_changed()
            return replace(node, init=init, cond=cond, step=step, body=body)
            
        return node
        
    # -------------------------------------------------
    # Ubicaciones y llamadas
    # -------------------------------------------------
    
    def visit_Name(self, node):
        return node
        
    def visit_Index(self, node):
        index = node.index.accept(self)
        if index is not node.index:
            self.mark_changed()
            return replace(node, index=index)
        return node
        
    def visit_Call(self, node):
        args = node.args.accept(self)
        if args is not node.args:
            self.mark_changed()
            return replace(node, args=args)
        return node
        
    '''def visit(self, node: ExprList):
        exprs = []
        local_changed = False
        
        for expr in node.exprs:
            new_expr = expr.accept(self)
            exprs.append(new_expr)
            if new_expr is not expr:
                local_changed = True
                
        if local_changed:
            self.mark_changed()
            return replace(node, exprs=exprs)
            
        return node'''
        
    # -------------------------------------------------
    # Literales
    # -------------------------------------------------
    
    def visit(self, node: Literal):
        return node
    
    # -------------------------------------------------
    # Expresiones
    # -------------------------------------------------
    
    def visit_BinOp(self, node):
        left = node.left.accept(self)
        right = node.right.accept(self)
        op = node.op
        
        # -----------------------------------------------
        # 1. Constant folding aritmético
        # -----------------------------------------------
        if same_literal_family(left, right):
            lv = value_of(left)
            rv = value_of(right)
            
            try:
                if is_number(left) and is_number(right):
                    template = left if is_float(left) or is_float(right) else left
                    
                    if op == "+":
                        self.mark_changed()
                        return make_number(lv + rv, template)
                    if op == "-":
                        self.mark_changed()
                        return make_number(lv - rv, template)
                    if op == "*":
                        self.mark_changed()
                        return make_number(lv * rv, template)
                    if op == "/" and rv != 0:
                        self.mark_changed()
                        if is_int(left) and is_int(right):
                            return Literal("integer", lv // rv, lineno=node.lineno)
                        return Literal("float", lv / rv, lineno=node.lineno)
                    if op == "%" and rv != 0 and is_int(left) and is_int(right):
                        self.mark_changed()
                        return Literal("integer", lv % rv, lineno=node.lineno)
                        
                # Relacionales con literales compatibles
                if op == "==":
                    self.mark_changed()
                    return Literal("boolean", lv == rv, lineno=node.lineno)
                if op == "!=":
                    self.mark_changed()
                    return Literal("boolean", lv != rv, lineno=node.lineno)
                if op == "<":
                    self.mark_changed()
                    return Literal("boolean", lv < rv, lineno=node.lineno)
                if op == "<=":
                    self.mark_changed()
                    return Literal("boolean", lv <= rv, lineno=node.lineno)
                if op == ">":
                    self.mark_changed()
                    return Literal("boolean", lv > rv, lineno=node.lineno)
                if op == ">=":
                    self.mark_changed()
                    return Literal("boolean", lv >= rv, lineno=node.lineno)
                    
            except Exception:
                # Si por alguna razón no puede plegar, conserva el árbol.
                pass
                
        # -----------------------------------------------
        # 2. Simplificación algebraica conservadora
        # -----------------------------------------------
        if op == "+":
            if is_zero(right):
                self.mark_changed()
                return left
            if is_zero(left):
                self.mark_changed()
                return right
                
        elif op == "-":
            if is_zero(right):
                self.mark_changed()
                return left
                
        elif op == "*":
            if is_one(right):
                self.mark_changed()
                return left
            if is_one(left):
                self.mark_changed()
                return right
                
            # Solo se elimina x si sabemos que no hay efectos laterales.
            if is_zero(right) and not has_side_effect(left):
                self.mark_changed()
                return right
            if is_zero(left) and not has_side_effect(right):
                self.mark_changed()
                return left
                
        elif op == "/":
            if is_one(right):
                self.mark_changed()
                return left
                
        elif op == "%":
            if is_one(right) and not has_side_effect(left):
                self.mark_changed()
                return Literal("integer", 0, lineno=node.lineno)
                
        # -----------------------------------------------
        # 3. Simplificación booleana
        # -----------------------------------------------
        elif op in ("&&", "and"):
            if is_bool(left) and left.value is False:
                self.mark_changed()
                return left
            if is_bool(left) and left.value is True:
                self.mark_changed()
                return right
            if is_bool(right) and right.value is False and not has_side_effect(left):
                self.mark_changed()
                return right
            if is_bool(right) and right.value is True:
                self.mark_changed()
                return left
                
        elif op in ("||", "or"):
            if is_bool(left) and left.value is True:
                self.mark_changed()
                return left
            if is_bool(left) and left.value is False:
                self.mark_changed()
                return right
            if is_bool(right) and right.value is True and not has_side_effect(left):
                self.mark_changed()
                return right
            if is_bool(right) and right.value is False:
                self.mark_changed()
                return left
                
        if left is not node.left or right is not node.right:
            self.mark_changed()
            return replace(node, left=left, right=right)
            
        return node
        
    def visit_UnaryOp(self, node):
        expr = node.expr.accept(self)
        op = node.oper
        
        if is_int(expr):
            if op == "-":
                self.mark_changed()
                return Literal("integer", -expr.value, lineno=node.lineno)
            if op == "+":
                self.mark_changed()
                return expr
                
        if is_float(expr):
            if op == "-":
                self.mark_changed()
                return Literal("float", -expr.value, lineno=node.lineno)
            if op == "+":
                self.mark_changed()
                return expr
                
        if is_bool(expr) and op in ("!", "not"):
            self.mark_changed()
            return Literal("boolean", not expr.value, lineno=node.lineno)
            
        if expr is not node.expr:
            self.mark_changed()
            return replace(node, expr=expr)
            
        return node
        
    def visit_TernaryOp(self, node):
        cond = node.cond.accept(self)
        then = node.then.accept(self)
        otherwise = node.otherwise.accept(self)
        
        # true ? a : b -> a
        # false ? a : b -> b
        if is_bool(cond):
            self.mark_changed()
            return then if cond.value else otherwise
            
        if cond is not node.cond or then is not node.then or otherwise is not node.otherwise:
            self.mark_changed()
            return replace(
            node,
            cond=cond,
            then=then,
            otherwise=otherwise,
            )
            
        return node
        
        
# ---------------------------------------------------
# API pública
# ---------------------------------------------------

def optimize_ast_o1(ast: Node, max_passes: int = 10, verbose: bool = False) -> Node:
    """
    Ejecuta O1 sobre el AST.
    
    Se hacen varias pasadas porque una optimización puede habilitar otra:
    
    (3 * 4) + 0
    12 + 0
    12
    """
    current = ast
    
    for passno in range(1, max_passes + 1):
        opt = ASTOptimizer()
        new_ast = current.accept(opt)
        
        if verbose:
            print(f"[O1] pasada {passno}: changed={opt.changed}")
            
        current = new_ast
        
        if not opt.changed:
            break
            
    return current

ast = Program([
    DeclInit(
        name = "x",
        typ = SimpleType(name="int"),
        init = BinOp(
            op = "+",
            left = Literal("integer", 3),
            right = BinOp(
                op = "*",
                left = Literal("integer", 4),
                right = Literal("integer", 2)
            )
        )
    ),
    DeclInit(
        name = "y",
        typ = SimpleType(name="int"),
        init = BinOp(
            op = "+",
            left = Name("x"),
            right = Literal("integer", 0)
        )
    ),
    DeclInit(
        name = "z",
        typ = SimpleType(name="int"),
        init = BinOp(
            op = "*",
            left = Name("y"),
            right = Literal("integer", 1)
        )
    ),
    DeclInit(
        name = "w",
        typ = SimpleType(name="int"),
        init = BinOp(
            op = "*",
            left = Name("z"),
            right = Literal("integer", 0)
        )
    ),
    If(
        cond = Literal("boolean", False),
        then = Block([
            Print(Literal("integer", 111))
        ]),
        otherwise = Block([
            Print(Literal("integer", 222))
        ])
    ),
    While(
        cond = Literal("boolean", False),
        body = Block([
            Print(Literal("integer", 999))
        ])
    ),
    DeclInit(
        name = "t",
        typ = SimpleType(name="int"),
        init = TernOp(
            cond = Literal("boolean", True),
            then = Literal("integer", 10),
            otherwise = Literal("integer", 20)
        )
    )
])

'''ast = Program([
    VarDecl(
        "x",
        IntegerType(),

        BinOp(
            "+",
            IntegerLiteral(value=3),

            BinOp(
                "*",
                IntegerLiteral(value=4),
                IntegerLiteral(value=2)
            )
        )
    ),

    VarDecl(
        "y",
        IntegerType(),

        BinOp(
            "+",
            VarLoc("x"),
            IntegerLiteral(value=0)
        )
    ),

    VarDecl(
        "z",
        IntegerType(),

        BinOp(
            "*",
            VarLoc("y"),
            IntegerLiteral(value=1)
        )
    ),

    VarDecl(
        "w",
        IntegerType(),

        BinOp(
            "*",
            VarLoc("z"),
            IntegerLiteral(value=0)
        )
    ),

    IfStmt(
        BooleanLiteral(value=True),

        Block([
            PrintStmt(
                IntegerLiteral(value=111)
            )
        ]),

        Block([
            PrintStmt(
                IntegerLiteral(value=222)
            )
        ])
    ),

    WhileStmt(
        BooleanLiteral(value=False),

        Block([
            PrintStmt(
                IntegerLiteral(value=999)
            )
        ])
    ),

    VarDecl(
        "t",
        IntegerType(),

        ConditionalExpr(
            BooleanLiteral(value=True),
            IntegerLiteral(value=10),
            IntegerLiteral(value=20)
        )
    )

])'''

print("===================================")
print("AST ORIGINAL")
print("===================================")
print(ast)

optimized = optimize_ast_o1(ast, verbose=True)

print()
print("===================================")
print("AST OPTIMIZADO")
print("===================================")
print(optimized)
