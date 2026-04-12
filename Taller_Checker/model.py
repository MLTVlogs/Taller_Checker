from dataclasses import dataclass
from typing import List, Any, Optional, Union

# CLASES DE NODOS
class Node:
	def __init__(self, name):
		self.name = name
	def accept(self, visitor):
		method_name = 'visit_' + self.__class__.__name__
		method = getattr(visitor, method_name, visitor.generic_visit)
		return method(self)
		

# ---------- Types ----------
class Type(Node):
	...

@dataclass(frozen=True)
class SimpleType(Type):
	name: str

@dataclass(frozen=True)
class ArrayType(Type):
	elem: Type

@dataclass(frozen=True)
class ArraySizedType(Type):
	size_expr: "Expr"
	elem: Type

@dataclass(frozen=True)
class FuncType(Type):
	ret: Type
	params: List["Param"]

@dataclass(frozen=True)
class Param(Node):
	name: str
	typ: Type

# ---------- Program / Decl ----------
class Decl(Node):
	...

@dataclass
class Program(Node):
	decls: List[Decl]

@dataclass
class DeclTyped(Decl):
	name: str
	typ: Type

@dataclass
class DeclInit(Decl):
	name: str
	typ: Type
	init: Any

@dataclass
class ClassDecl(Decl):
	name: str
	body: Optional[List[Decl]]

# ---------- Statement ----------
class Stmt(Node):
	...

@dataclass
class Print(Stmt):
	values: List["Expr"]

@dataclass
class Return(Stmt):
	value: Optional["Expr"]

@dataclass
class Break(Stmt):
	...

@dataclass
class Continue(Stmt):
	...

@dataclass
class Block(Stmt):
	stmts: List[Union[Stmt, Decl]]

@dataclass
class ExprStmt(Stmt):
	expr: "Expr"

@dataclass
class If(Stmt):
	cond: Optional["Expr"]
	then: Stmt
	otherwise: Optional[Stmt] = None

@dataclass
class For(Stmt):
	init: Optional["Expr"]
	cond: Optional["Expr"]
	step: Optional["Expr"]
	body: Stmt

@dataclass
class While(Stmt):
	cond: Optional["Expr"]
	body: Stmt

# ---------- Expressions ----------
class Expr(Node):
	...

@dataclass
class Name(Expr):
	id: str

@dataclass
class Literal(Expr):
	kind: str
	value: Any

@dataclass
class Index(Expr):
	base: Expr
	indices: List[Expr]

@dataclass
class Call(Expr):
	func: str
	args: List[Expr]

@dataclass
class MemberCall(Expr):
	target: str
	members: List[Expr]

@dataclass
class Assign(Expr):
	target:Expr
	value: Expr

@dataclass
class TernOp(Expr):
	cond: Expr
	then: Expr
	otherwise: Expr

@dataclass
class BinOp(Expr):
	op: str
	left: Expr
	right: Expr

@dataclass
class UnaryOp(Expr):
	op: str
	expr: Expr

@dataclass
class PrefixOp(Expr):
	op: str
	expr: Expr

@dataclass
class PostfixOp(Expr):
	op: str
	expr: Expr

@dataclass
class Constructor(Expr):
	type: str
	atts: List[Expr]