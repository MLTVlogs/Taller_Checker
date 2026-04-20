DOCUMENTACIÓN ANÁLISIS SEMÁNTICO

- cómo ejecutar el analizador semántico;
	EL analizador semántico tiene incorporado un método en main para hacer pruebas unitarias, para estas es necesario tener un archivo aparte con las líneas que se desea probar con el analizador semántico, luego se deberá usar el comando "python checker.py [nombreTest].bminor"

- cómo está implementada la tabla de símbolos;
    La tabla de simbolos revisa las declaraciones realizada en los scopes correspondientes mediante un ciclo el cual cada que encuentra una nueva declaracion revisa si esta misma ya existe y si lo hace llama al metodo SymbolDefinedError, en caso de que no exista pero no sea el tipo correspondiente llama al metodo SymbolConflictError 
	
- cómo está implementado el Visitor con multimethod;
    El visitor entra a cada uno de los nodos del arbol AST el cual ya en cada uno de los nodos tiene el metodo accept para que el visitor peuda entrar y seguir mas adelante en el arbol, este mismo va por cada uno de los nodos revisando la semantica del lenguaje y que las declaraciones esten definidas con el tipo correcto y una sola vez por scope gracias a las tablas de simbolos que revisa en el metodo open_scope

- qué tipos soporta el sistema;
     Soporta tipos como INT, FLOAT, CHAR, STRING, BOOLS y arrays de estos mismos


- qué chequeos semánticos fueron implementados;
    Checkeo de tipos en las variables y los copes de las mismas, declaraciones de funciones y tipos de sus argumentos, verificaciones de operaciones como la suma y resta, revisa el tipo de los argumentos de los if y while para verificar que son booleanos 

- qué aspectos quedaron pendientes, si los hay.
    Entendimiento total del grupo de la funcionalidad y sucesion de procedimientos del checker