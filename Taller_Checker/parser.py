# grammar.py (versión actualizada para nuevo AST)
import logging
import sly
from rich import print
from rich.tree import Tree
from lexer  import Lexer
from errors import error, errors_detected
from graphviz import Digraph
import uuid
from typing import List
from model import (
    Type, SimpleType, ArrayType, ArraySizedType, FuncType, Param,
    Decl, Program, DeclTyped, DeclInit, ClassDecl,
    Stmt, Print, Return, Break, Continue, Block, ExprStmt, If, For, While,
    Expr, Name, Literal, Index, Call, MemberCall, Assign, TernOp, BinOp, UnaryOp, PrefixOp, PostfixOp, Constructor
)

def _L(node, lineno):
	node.lineno = lineno
	return node	

# PARSER
class Parser(sly.Parser):
	log = logging.getLogger()
	log.setLevel(logging.ERROR)
	expected_shift_reduce = 1
	debugfile='grammar.txt'
	
	tokens = Lexer.tokens
	
	# =================================================
	# PROGRAMA
	# =================================================
	
	@_("decl_list")
	def prog(self, p):
		return _L(Program(p[0]), p.lineno)
	
	# =================================================
	# LISTAS DE DECLARACIONES
	# =================================================
	
	@_("decl decl_list")
	def decl_list(self, p):
		return [p[0]] + p[1]
		
	@_("empty")
	def decl_list(self, p):
		return []
		
	# =================================================
	# DECLARACIONES
	# =================================================
	
	@_("ID ':' type_simple ';'")
	def decl(self, p):
		return _L(DeclTyped(p[0],p[2]), p.lineno)
		
	@_("ID ':' type_array_sized ';'")
	def decl(self, p):
		return _L(DeclTyped(p[0],p[2]), p.lineno)
		
	@_("ID ':' type_func ';'")
	def decl(self, p):
		return _L(DeclTyped(p[0],p[2]), p.lineno)
	
	@_("class_decl")
	def decl(self, p):
		return p[0]
		
	@_("decl_init")
	def decl(self, p):
		return p[0]
	
	# === DECLARACIONES con inicialización
	
	@_("ID ':' type_simple '=' expr ';'")
	def decl_init(self, p):
		return _L(DeclInit(p[0],p[2],p[4]), p.lineno)
		
	@_("ID ':' CONSTANT '=' expr ';'")
	def decl_init(self, p):
		return _L(DeclInit(p[0],SimpleType("const"),p[4]), p.lineno)
		
	@_("ID ':' type_array_sized '=' '{' opt_expr_list '}' ';'")
	def decl_init(self, p):
		return _L(DeclInit(p[0],p[2],p[5]), p.lineno)
		
	@_("ID ':' type_func '=' '{' opt_stmt_list '}'")
	def decl_init(self, p):
		return _L(DeclInit(p[0],p[2],p[5]), p.lineno)
	
	# === DECLARACIONES de clases

	@_("ID ':' CLASS '=' '{' opt_class_body '}'")
	def class_decl(self, p):
		return _L(ClassDecl(p[0], p[5]), p.lineno)
	
	@_("class_body")
	def opt_class_body(self, p):
		return p[0]
	
	@_("empty")
	def opt_class_body(self, p):
		return []

	@_("class_member class_body")
	def class_body(self, p):
		return p[0] + p[1]

	@_("class_member")
	def class_body(self, p):
		return p[0]
	
	@_("decl")
	def class_member(self, p):
		return [p[0]]
		
	# =================================================
	# STATEMENTS
	# =================================================
	
	@_("stmt_list")
	def opt_stmt_list(self, p):
		return p[0]
		
	@_("empty")
	def opt_stmt_list(self, p):
		return []
		
	@_("stmt stmt_list")
	def stmt_list(self, p):
		return [p[0]] + p[1]
		
	@_("stmt")
	def stmt_list(self, p):
		return [p[0]]
		
	@_("open_stmt")
	@_("closed_stmt")
	def stmt(self, p):
		return p[0]

	@_("if_stmt_closed")
	@_("for_stmt_closed")
	@_("while_stmt_closed")
	@_("simple_stmt")
	def closed_stmt(self, p):
		return p[0]

	@_("if_stmt_open")
	@_("for_stmt_open")
	@_("while_stmt_open")
	def open_stmt(self, p):
		return p[0]

	# -------------------------------------------------
	# IF
	# -------------------------------------------------
	
	@_("IF '(' opt_expr ')'")
	def if_cond(self, p):
		return p[2]
		
	@_("if_cond closed_stmt ELSE closed_stmt")
	def if_stmt_closed(self, p):
		return _L(If(p[0],p[1],p[3]), p.lineno)
		
	@_("if_cond stmt")
	def if_stmt_open(self, p):
		return _L(If(p[0],p[1]), p.lineno)
		
	@_("if_cond closed_stmt ELSE if_stmt_open")
	def if_stmt_open(self, p):
		return _L(If(p[0],p[1],p[3]), p.lineno)
		
	# -------------------------------------------------
	# FOR
	# -------------------------------------------------
	
	@_("FOR '(' opt_expr ';' opt_expr ';' opt_expr ')'")
	def for_header(self, p):
		return (p[2], p[4], p[6])
		
	@_("for_header open_stmt")
	def for_stmt_open(self, p):
		return _L(For(p[0][0],p[0][1],p[0][2],p[2]), p.lineno)
		
	@_("for_header closed_stmt")
	def for_stmt_closed(self, p):
		return _L(For(p[0][0],p[0][1],p[0][2],p[1]), p.lineno)
		
	# -------------------------------------------------
	# WHILE
	# -------------------------------------------------
	
	@_("WHILE '(' opt_expr ')'")
	def while_cond(self, p):
		return p[2]

	@_("while_cond open_stmt")
	def while_stmt_open(self, p):
		return _L(While(p[0],p[1]), p.lineno)
		
	@_("while_cond closed_stmt")
	def while_stmt_closed(self, p):
		return _L(While(p[0],p[1]), p.lineno)
		
	# -------------------------------------------------
	# SIMPLE STATEMENTS
	# -------------------------------------------------
	
	@_("print_stmt")
	@_("return_stmt")
	@_("break_stmt")
	@_("continue_stmt")
	@_("block_stmt")
	@_("decl")
	@_("expr ';'")
	def simple_stmt(self, p):
		return p[0]

	# PRINT
	@_("PRINT opt_expr_list ';'")
	def print_stmt(self, p):
		return _L(Print(p[1]), p.lineno)
		
	# RETURN
	@_("RETURN opt_expr ';'")
	def return_stmt(self, p):
		return _L(Return(p[1]), p.lineno)

	@_("BREAK ';'")
	def break_stmt(self, p):
		return _L(Break(), p.lineno)

	@_("CONTINUE ';'")
	def continue_stmt(self, p):
		return _L(Continue(), p.lineno)

	# BLOCK
	@_("'{' stmt_list '}'")
	def block_stmt(self, p):
		return _L(Block(p[1]), p.lineno)
		
	# =================================================
	# EXPRESIONES
	# =================================================
	
	@_("empty")
	def opt_expr_list(self, p):
		return []
		
	@_("expr_list")
	def opt_expr_list(self, p):
		return p[0]
		
	@_("expr ',' expr_list")
	def expr_list(self, p):
		return [p[0]] + p[2]
		
	@_("expr")
	def expr_list(self, p):
		return [p[0]]
		
	@_("empty")
	def opt_expr(self, p):
		return None
		
	@_("expr")
	def opt_expr(self, p):
		return p[0]
		
	# -------------------------------------------------
	# PRIMARY
	# -------------------------------------------------
	
	@_("expr1")
	def expr(self, p):
		return p[0]
		
	@_("lval  '='  expr1")
	@_("lval ADDEQ expr1")
	@_("lval SUBEQ expr1")
	@_("lval MULEQ expr1")
	@_("lval DIVEQ expr1")
	@_("lval MODEQ expr1")
	def expr1(self, p):
		return _L(Assign(p[0],p[2]), p.lineno)
		
	@_("expr2")
	def expr1(self, p):
		return p[0]
		
	# ----------- LVALUES -------------------
	
	@_("ID")
	def lval(self, p):
		return _L(Name(p[0]),p.lineno)
		
	@_("ID index")
	def lval(self, p):
		return _L(Index(p[0],p[1]),p.lineno)
		
	# -------------------------------------------------
	# OPERADORES
	# -------------------------------------------------

	@_("expr2 '?' expr3 ':' expr3")
	def expr2(self, p):
		return _L(TernOp(p[0],p[2],p[4]),p.lineno)

	@_("expr3")
	def expr2(self, p):
		return p[0]
	
	@_("expr3 LOR expr4")
	def expr3(self, p):
		return _L(BinOp(p[1],p[0],p[2]),p.lineno)
		
	@_("expr4")
	def expr3(self, p):
		return p[0]
		
	@_("expr4 LAND expr5")
	def expr4(self, p):
		return _L(BinOp(p[1],p[0],p[2]),p.lineno)
		
	@_("expr5")
	def expr4(self, p):
		return p[0]
		
	@_("expr5 EQ expr6")
	@_("expr5 NE expr6")
	@_("expr5 LT expr6")
	@_("expr5 LE expr6")
	@_("expr5 GT expr6")
	@_("expr5 GE expr6")
	def expr5(self, p):
		return _L(BinOp(p[1],p[0],p[2]),p.lineno)

	@_("expr6")
	def expr5(self, p):
		return p[0]
		
	@_("expr6 '+' expr7")
	@_("expr6 '-' expr7")
	def expr6(self, p):
		return _L(BinOp(p[1],p[0],p[2]),p.lineno)
		
	@_("expr7")
	def expr6(self, p):
		return p[0]
		
	@_("expr7 '*' expr8")
	@_("expr7 '/' expr8")
	@_("expr7 '%' expr8")
	def expr7(self, p):
		return _L(BinOp(p[1],p[0],p[2]),p.lineno)
		
	@_("expr8")
	def expr7(self, p):
		return p[0]
		
	@_("expr8 '^' expr9")
	def expr8(self, p):
		return _L(BinOp(p[1],p[0],p[2]),p.lineno)
		
	@_("expr9")
	def expr8(self, p):
		return p[0]
		
	@_("'-' expr9")
	@_("'!' expr9")
	def expr9(self, p):
		return _L(UnaryOp(p[0],p[1]),p.lineno)

	@_("expr10")
	def expr9(self, p):
		return p[0]

	@_("postfix")
	def expr10(self, p):
		return p[0]

	@_("primary")
	def postfix(self, p):
		return p[0]

	@_("postfix INC")
	def postfix(self, p):
		return _L(PostfixOp(p[0],p[1]),p.lineno)

	@_("postfix DEC")
	def postfix(self, p):
		return _L(PostfixOp(p[0],p[1]),p.lineno)

	@_("prefix")
	def primary(self, p):
		return p[0]

	@_("INC prefix")
	def prefix(self, p):
		return _L(PrefixOp(p[0],p[1]),p.lineno)

	@_("DEC prefix")
	def prefix(self, p):
		return _L(PrefixOp(p[0],p[1]),p.lineno)

	@_("group")
	def prefix(self, p):
		return p[0]
		
	@_("'(' expr ')'")
	def group(self, p):
		return (p[1])

	@_("ID '(' opt_expr_list ')'")
	def group(self, p):
		return _L(Call(p[0],p[2]), p.lineno)
		
	@_("ID index")
	def group(self, p):
		return _L(Index(p[0],p[1]),p.lineno)
	
	@_("ID member_acc_list")
	def group(self, p):
		return _L(MemberCall(p[0],p[1]), p.lineno)

	@_("NEW type_simple '(' opt_expr_list ')'")
	def group(self, p):
		return _L(Constructor(p[1],p[3]), p.lineno)
		
	@_("factor")
	def group(self, p):
		return p[0]
		
	# INDICE DE ARREGLO
	@_("'[' expr ']'")
	def index(self, p):
		return [p[1]]
	
	# ------------------------------------------------
	# ACCESO A MIEMBROS
	# ------------------------------------------------
	@_("member_acc")
	def member_acc_list(self, p):
		return [p[0]]
	
	@_("member_acc_list member_acc")
	def member_acc_list(self, p):
		return p[0] + [p[1]]
	
	@_("'.' ID")
	def member_acc(self, p):
		return _L(Name(p[1]), p.lineno)

	@_("'.' ID index")
	def member_acc(self, p):
		return _L(Index(p[1],p[2]), p.lineno)

	@_("'.' ID '(' opt_expr_list ')'")
	def member_acc(self, p):
		return _L(Call(p[1],p[3]), p.lineno)

	# -------------------------------------------------
	# FACTORES
	# -------------------------------------------------
	
	@_("ID")
	def factor(self, p):
		return _L(Name(p[0]), p.lineno)
		
	@_("INTEGER_LITERAL")
	def factor(self, p):
		return _L(Literal("int", p[0]), p.lineno)
		
	@_("FLOAT_LITERAL")
	def factor(self, p):
		return _L(Literal("float", p[0]), p.lineno)
		
	@_("CHAR_LITERAL")
	def factor(self, p):
		return _L(Literal("char", p[0]), p.lineno)
		
	@_("STRING_LITERAL")
	def factor(self, p):
		return _L(Literal("string", p[0]), p.lineno)
		
	@_("TRUE", "FALSE")
	def factor(self, p):
		return _L(Literal("bool", p[0]), p.lineno)
		
	# =================================================
	# TIPOS
	# =================================================
	
	@_("INTEGER")
	@_("FLOAT")
	@_("BOOLEAN")
	@_("CHAR")
	@_("STRING")
	@_("VOID")
	@_("ID")
	def type_simple(self, p):
		return SimpleType(p[0])
		
	@_("ARRAY '[' ']' type_simple")
	@_("ARRAY '[' ']' type_array")
	def type_array(self, p):
		return ArrayType(p[3])
		
	@_("ARRAY index type_simple")
	@_("ARRAY index type_array_sized")
	def type_array_sized(self, p):
		return ArraySizedType(p[1], p[2])
		
	@_("FUNCTION type_simple '(' opt_param_list ')'")
	@_("FUNCTION type_array_sized '(' opt_param_list ')'")
	def type_func(self, p):
		return FuncType(p[1], p[3])
		
	@_("empty")
	def opt_param_list(self, p):
		return []
		
	@_("param_list")
	def opt_param_list(self, p):
		return p[0]
		
	@_("param_list ',' param")
	def param_list(self, p):
		return p[0] + [p[2]]
		
	@_("param")
	def param_list(self, p):
		return [p[0]]
		
	@_("ID ':' type_simple")
	def param(self, p):
		return Param(p[0], p[2])
		
	@_("ID ':' type_array")
	def param(self, p):
		return Param(p[0], p[2])
		
	@_("ID ':' type_array_sized")
	def param(self, p):
		return Param(p[0], p[2])
		
	# =================================================
	# UTILIDAD: EMPTY
	# =================================================
	
	@_("")
	def empty(self, p):
		pass
		
	def error(self, p):
		lineno = p.lineno if p else 'EOF'
		value = repr(p.value) if p else 'EOF'
		error(f'Syntax error at {value}', lineno)
		

# AST Rich Tree
def build_rich_tree(node):
	label = type(node).__name__
	tree = Tree(label)

	for key, value in vars(node).items():
		if isinstance(value, List):
			for item in value:
				tree.add(build_rich_tree(item))
		if hasattr(value, "__dict__"):
			tree.add(build_rich_tree(value))
		else:
			tree.add(f"{key}: {value}")
	
	return tree

# AST a Graphviz
def ast_to_graphviz(node, dot, parent_id=None):
    node_id = str(uuid.uuid4())
    label = type(node).__name__

    dot.node(node_id, label)

    if parent_id:
        dot.edge(parent_id, node_id)

    for field, value in vars(node).items():
        if isinstance(value, list):
            for item in value:
                ast_to_graphviz(item, dot, node_id)
        elif hasattr(value, "__dict__"):
            ast_to_graphviz(value, dot, node_id)

    return dot

def parse(txt):
	l = Lexer()
	p = Parser()	
	return p.parse(l.tokenize(txt))
	
if __name__ == '__main__':
	import sys
	
	if len(sys.argv) != 3: raise SystemExit("Usage: python parser.py -graphviz <filename> or python parser.py -rich <filename>")
			
	filename = sys.argv[2]
		
	if filename:
		txt = open(filename, encoding='utf-8').read()
		try:
			ast = parse(txt)
		except Exception:
			pass
		else:
			if "-graphviz" in sys.argv:
				graph = Digraph()
				ast_to_graphviz(ast, graph)
				graph.render(f'{filename.rstrip(".bminor")}_ast', format='png', cleanup=True)
			elif "-rich" in sys.argv:
				tree = build_rich_tree(ast)
				print(tree)