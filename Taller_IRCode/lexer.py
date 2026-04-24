# lexer.py
# -*- coding: utf-8 -*-

import sly

from errors import error, errors_detected

class LexicalError(Exception):
	...

class Lexer(sly.Lexer):
	tokens = {
		# keywords
		ARRAY, AUTO, BOOLEAN, CHAR, CLASS, CONSTANT,ELSE, FALSE, 
		FLOAT, FOR, FUNCTION, IF, INTEGER, NEW, PRINT, RETURN,
		STRING, TRUE, VOID, WHILE, BREAK, CONTINUE,
		
		# operator
		LT, LE, GT, GE, EQ, NE, LAND, LOR, INC, DEC,
		
		ADDEQ, SUBEQ, MULEQ, DIVEQ, MODEQ,
		
		# other tokens
		ID, CHAR_LITERAL, FLOAT_LITERAL, INTEGER_LITERAL, STRING_LITERAL
	}
	literals = '+-*/%^=:;.,()[]{}!?'

	# ignore
	ignore = ' \t\r'

	# ignore newline
	@_(r"\n+")
	def ignore_newline(self, t):
		self.lineno += t.value.count('\n')
		
	# ignore comentarios
	@_(r"\/\/[^\n]*")
	def ignore_cppcomment(self, t):
		pass
		
	@_(r"\/\*[^*]*\*(\*|[^*/][^*]*\*)*\/")
	def ignore_comment(self, t):
		self.lineno += t.value.count('\n')

	@_(r"/\*(.|\n)*?")
	def malformed_comment(self, t):
		error("Comentario mal formado, sin cerrar", t.lineno)

	# Operadores de relacion
	LE   = r'<='
	GE   = r'>='
	EQ   = r'=='
	NE   = r'!='
	LT   = r'<'
	GT   = r'>'

	# Operadores Logicos
	LAND = r'&&'
	LOR  = r'\|\|'
	
	INC  = r'\+\+'
	DEC  = r'--'
	
	ADDEQ = r'\+='
	SUBEQ = r'-='
	MULEQ = r'\*='
	DIVEQ = r'/='
	MODEQ = r'%='
	
	# Definicion de Tokens
	ID   = r'[a-zA-Z_]\w*'
	
	ID['array']    = ARRAY
	ID['auto']     = AUTO
	ID['boolean']  = BOOLEAN
	ID['char']     = CHAR
	ID['class']    = CLASS
	ID['constant'] = CONSTANT
	ID['else']     = ELSE
	ID['false']    = FALSE
	ID['float']    = FLOAT
	ID['for']      = FOR
	ID['function'] = FUNCTION
	ID['if']       = IF
	ID['integer']  = INTEGER
	ID['new']	   = NEW
	ID['print']    = PRINT
	ID['return']   = RETURN
	ID['string']   = STRING
	ID['true']     = TRUE
	ID['void']     = VOID
	ID['while']    = WHILE
	ID['break']    = BREAK
	ID['continue'] = CONTINUE

	
	@_(r"'([\x20-\x7E]|\\([abefnrtv\\'\"]|0x[0-9A-Fa-f]{2}))'")
	def CHAR_LITERAL(self, t):
		t.value = t.value[1:-1]
		if t.value == '\\n': t.value = '\n'
		return t
	
	@_(r"'.")
	def malformed_char(self, t):
		error(f"malformado CHAR", t.lineno)
	
	@_(r"\d*(\.\d+)?[eE][-+]?[1-9]\d*|\d*\.\d+")
	def FLOAT_LITERAL(self, t):
		t.value = float(t.value)
		return t
		
	@_(r'(0\d+)((\.\d+(e[-+]?\d+)?)|(e[-+]?\d+))')
	def malformed_float(self, t):
		error(f"Literal de punto flotante '{t.value}' no sportado", t.lineno)
		
	@_(r"[1-9]\d*|0")
	def INTEGER_LITERAL(self, t):
		t.value = int(t.value)
		return t

	@_(r'0\d+')
	def malformed_integer(self, t):
		error(f"Literal entera '{t.value}' no sportado", t.lineno)

	@_(r'\"([^"\\]*(\\.[^"\\]*)*)\"')
	def STRING_LITERAL(self, t):
		t.value = t.value[1:-1]
		return t
	
	def error(self, t):
		#print(f"Línea {self.lineno}: Caracter Inválido {t.value[0]}")
		error(f"Caracter Ilegal '{t.value[0]}'", t.lineno)
		self.index += 1



def tokenize(filename:str):
	from rich.table   import Table
	from rich.console import Console
	
	txt = open(filename, encoding='utf-8').read()
	lex = Lexer()
	
	table = Table(title='Análisis Léxico')
	table.add_column('type')
	table.add_column('value')
	table.add_column('lineno', justify='right')
	
	for tok in lex.tokenize(txt):
		value = tok.value if isinstance(tok.value, str) else str(tok.value)
		table.add_row(tok.type, value, str(tok.lineno))
		# print(tok)

	if not errors_detected():
		console = Console()
		console.print(table)


if __name__ == '__main__':
	import sys
	
	if sys.platform != 'ios':
		
		if len(sys.argv) != 2:
			raise SystemExit("Usage: python lexer.py <filename>")
		
		filename = sys.argv[1]

	if filename:
		tokenize(filename)
