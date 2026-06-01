"""
Pipeline completo de compilación e interpretación para .bminor

Uso:
    python main.py tests/test1.bminor     # Compilar y ejecutar un archivo
    python main.py tests/test1.bminor 1   # Con optimización
    python main.py                         # Ejecutar todos los tests
"""

import sys
from pathlib import Path

# Importar todos los módulos del pipeline
from lexer import Lexer
from parser import Parser
from checker import Checker
from ircode import IRCodeGen
from iroptimizer import IROptimizer
from irinterp import IRInterpreter


def compile_and_run(filename: str, optimize_level: int = 0, trace: bool = False, verbose: bool = True):
    """
    Compilar y ejecutar un archivo .bminor completamente.
    
    Args:
        filename: Ruta al archivo .bminor
        optimize_level: 0=sin optimización, 1=optimización básica, 2=avanzada
        trace: True para ver ejecución paso a paso del intérprete
        verbose: True para mostrar progreso
    
    Returns:
        Tupla (éxito: bool, resultado: Any)
    """
    if verbose:
        print(f"\n{'='*60}")
        print(f"[Compilando] {filename}")
        print('='*60)
    
    try:
        # Paso 1: Leer archivo
        if verbose:
            print("[1/6] Leyendo archivo...", end=" ", flush=True)
        with open(filename) as f:
            code = f.read()
        if verbose:
            print("OK")
        
        # Paso 2: Lexer + Parser
        if verbose:
            print("[2/6] Parseando...", end=" ", flush=True)
        lexer = Lexer()
        parser_instance = Parser()
        program_ast = parser_instance.parse(lexer.tokenize(code))
        if verbose:
            print("OK")
        
        # Paso 3: Checker (análisis semántico)
        if verbose:
            print("[3/6] Checkeando tipos...", end=" ", flush=True)
        checker = Checker.check(program_ast)
        if checker.errors:
            if verbose:
                print("\n[ERROR] Errores de tipo encontrados:")
                for error in checker.errors:
                    print(f"     {error}")
            return (False, None)
        if verbose:
            print("OK")
        
        # Paso 4: Generación de IR
        if verbose:
            print("[4/6] Generando IR...", end=" ", flush=True)
        ir_program = IRCodeGen.generate(program_ast)
        if verbose:
            print("OK")
        
        # Paso 5 (opcional): Optimización
        if optimize_level > 0:
            if verbose:
                print(f"[5/6] Optimizando (nivel {optimize_level})...", end=" ", flush=True)
            ir_program = IROptimizer.optimize(ir_program, level=optimize_level)
            if verbose:
                print("OK")
        
        # Paso 6: Interpretación
        if verbose:
            print("[6/6] Ejecutando...", end=" ", flush=True)
        if verbose:
            print("\n" + "-"*60)
            print("[SALIDA DEL PROGRAMA]")
            print("-"*60)
        
        interp = IRInterpreter(ir_program, trace=trace)
        result = interp.run("main")
        
        if verbose:
            print("-"*60)
            print(f"[OK] Compilacion exitosa - Resultado: {result}")
        
        return (True, result)
        
    except Exception as e:
        if verbose:
            print(f"\n[ERROR] Error: {e}")
            import traceback
            traceback.print_exc()
        return (False, None)


def run_all_tests():
    """Ejecutar todos los tests en la carpeta tests/"""
    main_dir = Path(__file__).parent
    test_dir = main_dir / "tests"  # ✅ Busca relativo a main.py
    
    if not test_dir.exists():
        print(f"[ERROR] No se encontró carpeta 'tests'")
        return
    
    test_files = sorted(test_dir.glob("*.bminor"))
    if not test_files:
        print(f"[ERROR] No se encontraron archivos .bminor en tests/")
        return
    
    results = []
    passed = 0
    failed = 0
    
    for test_file in test_files:
        try:
            success, result = compile_and_run(str(test_file), optimize_level=1, verbose=False, trace=True)
        except Exception as e:
            success = False
            result = None
        
        results.append((test_file.name, success, result))
        if success:
            passed += 1
        else:
            failed += 1
    
    print(f"\n{'='*60}")
    print("[RESUMEN DE TESTS]")
    print('='*60)
    for name, success, result in results:
        status = "[OK]" if success else "[FAIL]"
        print(f"  {status} {name:<20} -> {result}")
    
    print('='*60)
    print(f"[RESULTADOS] {passed} pasaron, {failed} fallaron")
    print('='*60)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Ejecutar archivo específico
        filename = sys.argv[1]
        optimize_level = int(sys.argv[2]) if len(sys.argv) > 2 else 0
        trace = "--trace" in sys.argv
        
        success, result = compile_and_run(filename, optimize_level=optimize_level, trace=trace, verbose=True)
        sys.exit(0 if success else 1)
    else:
        # Ejecutar todos los tests
        run_all_tests()