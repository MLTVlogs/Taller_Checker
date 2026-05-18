from __future__ import annotations

from typing import Any, Optional
from rich import print
from ircode import IRProgram, IRFunction, Instruction, IRCodeGen


class IROptimizer:
    def __init__(self, level: int = 0):
        self.level = level

    @classmethod
    def optimize(cls, program: IRProgram, level: int = 0) -> IRProgram:
        return cls(level).visit_program(program)

    def visit_program(self, program: IRProgram) -> IRProgram:
        if self.level <= 0:
            return program

        new_globals = list(program.globals)
        new_functions: list[IRFunction] = []

        for fn in program.functions:
            new_insts = self.optimize_instruction_list(fn.instructions)
            new_functions.append(
                IRFunction(
                    name=fn.name,
                    params=list(fn.params),
                    return_type=fn.return_type,
                    instructions=new_insts,
                )
            )

        return IRProgram(globals=new_globals, functions=new_functions)

    def optimize_instruction_list(self, instructions: list[Instruction]) -> list[Instruction]:
        insts = list(instructions)

        if self.level >= 1:
            insts = self.constant_fold_and_simplify(insts)
            insts = self.remove_unreachable(insts)
            insts = self.remove_branch_to_next_label(insts)

        if self.level >= 2:
            insts = self.remove_unused_temp_definitions(insts)

        return insts

    # -------------------------------------------------
    # Nivel O1
    # -------------------------------------------------

    def constant_fold_and_simplify(self, instructions: list[Instruction]) -> list[Instruction]:
        const: dict[str, Any] = {}
        out: list[Instruction] = []

        for inst in instructions:
            op = inst[0]

            if op in {"MOVI", "MOVF", "MOVB"} and len(inst) == 3:
                value, dst = inst[1], inst[2]
                const[dst] = value
                out.append(inst)
                continue

            if op in {"ADDI", "SUBI", "MULI", "DIVI", "ADDF", "SUBF", "MULF", "DIVF"} and len(inst) == 4:
                a, b, dst = inst[1], inst[2], inst[3]

                if a in const and b in const:
                    a_val, b_val = const[a], const[b]
                    if op == "ADDI":
                        result = a_val + b_val
                    elif op == "SUBI":
                        result = a_val - b_val
                    elif op == "MULI":
                        result = a_val * b_val
                    elif op == "DIVI":
                        if b_val != 0:
                            result = a_val // b_val
                        else:
                            result = None
                    elif op == "ADDF":
                        result = a_val + b_val
                    elif op == "SUBF":
                        result = a_val - b_val
                    elif op == "MULF":
                        result = a_val * b_val
                    elif op == "DIVF":
                        if b_val != 0.0:
                            result = a_val / b_val
                        else:
                            result = None
                    else:
                        result = None
                    
                    if result is not None:
                        if op.endswith("I"):
                            out.append(("MOVI", result, dst))
                            const[dst] = result
                        elif op.endswith("F"):
                            out.append(("MOVF", result, dst))
                            const[dst] = result
                        continue

                if op in {"ADDI", "ADDF"}:
                    if a in const and const[a] == 0:
                        out.append(("MOVI" if op.endswith("I") else "MOVF", b, dst))
                        const[dst] = const[b]
                    elif b in const and const[b] == 0:
                        out.append(("MOVI" if op.endswith("I") else "MOVF", a, dst))
                        const[dst] = const[a]
                    continue
                elif op in {"SUBI", "SUBF"}:
                    if b in const and const[b] == 0:
                        out.append(("MOVI" if op.endswith("I") else "MOVF", a, dst))
                        const[dst] = const[a]
                    continue
                elif op in {"MULI", "MULF"}:
                    if a in const and const[a] == 1:
                        out.append(("MOVI" if op.endswith("I") else "MOVF", b, dst))
                        const[dst] = const[b]
                    elif a in const and const[a] == 0:
                        out.append(("MOVI" if op.endswith("I") else "MOVF", 0, dst))
                        const[dst] = 0
                    elif b in const and const[b] == 1:
                        out.append(("MOVI" if op.endswith("I") else "MOVF", a, dst))
                        const[dst] = const[a]
                    elif b in const and const[b] == 0:
                        out.append(("MOVI" if op.endswith("I") else "MOVF", 0, dst))
                        const[dst] = 0
                    continue
                elif op in {"DIVI", "DIVF"}:
                    if b in const and const[b] == 1:
                        out.append(("MOVI" if op.endswith("I") else "MOVF", a, dst))
                        const[dst] = const[a]
                    continue
                    
                const.pop(dst, None)
                out.append(inst)
                continue

            if op in {"CMPI", "CMPF", "CMPB"} and len(inst) == 5:
                cmp_oper, a, b, dst = inst[1], inst[2], inst[3], inst[4]

                if a in const and b in const:
                    a_val, b_val = const[a], const[b]
                    if cmp_oper in {"==", "!=", "<", "<=", ">", ">="}:
                        result = 1 if self.eval_cmp(cmp_oper, a_val, b_val) else 0
                        out.append(("MOVI", result, dst))
                        const[dst] = result
                    continue

                const.pop(dst, None)
                out.append(inst)
                continue

            if op == "CBRANCH" and len(inst) == 4:
                test, true_label, false_label = inst[1], inst[2], inst[3]

                if test in const:
                    if const[test]:
                        out.append(("BRANCH", true_label))
                    else:
                        out.append(("BRANCH", false_label))
                    continue

                out.append(inst)
                continue

            # Instrucciones conservadoras.
            if len(inst) >= 2 and isinstance(inst[-1], str) and inst[-1].startswith("R"):
                const.pop(inst[-1], None)

            out.append(inst)

        return out

    def remove_unreachable(self, instructions: list[Instruction]) -> list[Instruction]:
        out: list[Instruction] = []
        unreachable = False

        for inst in instructions:
            op = inst[0]

            if op == "LABEL":
                unreachable = False
            if unreachable:
                continue
            if op in {"BRANCH", "RET"}:
                unreachable = True

            out.append(inst)

        return out

    def remove_branch_to_next_label(self, instructions: list[Instruction]) -> list[Instruction]:
        out: list[Instruction] = []
        i = 0

        while i < len(instructions):
            inst = instructions[i]

            if inst[0] == "BRANCH" and i + 1 < len(instructions):
                target_label = inst[1]
                next_inst = instructions[i + 1]
                if next_inst[0] == "LABEL" and next_inst[1] == target_label:
                    i += 1  # Saltar el BRANCH
                    continue

            out.append(inst)
            i += 1

        return out

    # -------------------------------------------------
    # Nivel O2
    # -------------------------------------------------

    def remove_unused_temp_definitions(self, instructions: list[Instruction]) -> list[Instruction]:
        used: set[str] = set()
        result_reversed: list[Instruction] = []

        for inst in reversed(instructions):
            dst = self.defined_temp(inst)
            args = self.used_temps(inst)

            if dst is not None:
                if dst not in used and self.is_pure_definition(inst):
                    continue

            used.difference_update({dst} if dst is not None else set())
            used.update(args)

            result_reversed.append(inst)

        return list(reversed(result_reversed))

    def defined_temp(self, inst: Instruction) -> Optional[str]:
        op = inst[0]

        if op in {"MOVI", "MOVF", "MOVB", "ADDR"} and len(inst) == 3:
            return inst[2] if isinstance(inst[2], str) and inst[2].startswith("R") else None

        if op in {"ADDI", "SUBI", "MULI", "DIVI", "ADDF", "SUBF", "MULF", "DIVF", "AND", "OR", "XOR"} and len(inst) == 4:
            return inst[3] if isinstance(inst[3], str) and inst[3].startswith("R") else None

        if op in {"CMPI", "CMPF", "CMPB"} and len(inst) == 5:
            return inst[4] if isinstance(inst[4], str) and inst[4].startswith("R") else None

        if op.startswith("LOAD") and len(inst) == 3:
            return inst[2] if isinstance(inst[2], str) and inst[2].startswith("R") else None

        return None

    def used_temps(self, inst: Instruction) -> set[str]:
        op = inst[0]

        if op in {"MOVI", "MOVF", "MOVB", "LABEL", "BRANCH", "DATAS", "ADDR"}:
            return set()

        if op.startswith("STORE"):
            return self.temps_in(inst[1:2])

        if op.startswith("PRINT"):
            return self.temps_in(inst[1:])

        if op == "CBRANCH":
            return self.temps_in(inst[1:2])

        if op == "RET":
            return self.temps_in(inst[1:])

        if op in {"ADDI", "SUBI", "MULI", "DIVI", "ADDF", "SUBF", "MULF", "DIVF", "AND", "OR", "XOR"}:
            return self.temps_in(inst[1:3])

        if op in {"CMPI", "CMPF", "CMPB"}:
            return self.temps_in(inst[2:4])

        return self.temps_in(inst[1:])

    def temps_in(self, values) -> set[str]:
        return {x for x in values if isinstance(x, str) and x.startswith("R")}

    def is_pure_definition(self, inst: Instruction) -> bool:
        op = inst[0]
        return (
            op in {
                "MOVI", "MOVF", "MOVB", "ADDR",
                "ADDI", "SUBI", "MULI", "DIVI",
                "ADDF", "SUBF", "MULF", "DIVF",
                "AND", "OR", "XOR",
                "CMPI", "CMPF", "CMPB",
            }
            or op.startswith("LOAD")
        )

    # -------------------------------------------------
    # Helpers
    # -------------------------------------------------

    def eval_cmp(self, oper: str, a: Any, b: Any) -> bool:
        if oper == "==":
            return a == b
        if oper == "!=":
            return a != b
        if oper == "<":
            return a < b
        if oper == "<=":
            return a <= b
        if oper == ">":
            return a > b
        if oper == ">=":
            return a >= b
        raise NotImplementedError(f"Comparador no soportado: {oper}")
    
def optimize_insts(insts, level):
    fn = IRFunction("main", [], None, insts)
    program = IRProgram([], [fn])
    opt = IROptimizer.optimize(program, level=level)
    return opt.functions[0].instructions
    
if __name__ == "__main__":
    import sys
    from checker import semantic_check
    from astopt import optimize_ast_o1

    if "-O0" in sys.argv:
        filename = sys.argv[1]
        with open(filename, encoding="utf-8") as f:
            txt = f.read()
            check, errors, ast = semantic_check(txt)
            if not check:
                print("Errores semánticos:")
                for err in errors:
                    print(err)
                    sys.exit(1)
            else:
                ir = IRCodeGen.generate(ast)
                irO0 = IROptimizer.optimize(ir, level=0)
                print(irO0.format())
    elif "-O1" in sys.argv:
        filename = sys.argv[1]
        with open(filename, encoding="utf-8") as f:
            txt = f.read()
            check, errors, ast = semantic_check(txt)
            if not check:
                print("Errores semánticos:")
                for err in errors:
                    print(err)
                    sys.exit(1)
            else:
                ir = IRCodeGen.generate(ast)
                irO1 = IROptimizer.optimize(ir, level=1)
                print(irO1.format())
    elif "-O2" in sys.argv:
        filename = sys.argv[1]
        with open(filename, encoding="utf-8") as f:
            txt = f.read()
            check, errors, ast = semantic_check(txt)
            if not check:
                print("Errores semánticos:")
                for err in errors:
                    print(err)
                    sys.exit(1)
            else:
                ir = IRCodeGen.generate(ast)
                irO2 = IROptimizer.optimize(ir, level=2)
                print(irO2.format())
    else:
        print("Si desea ejecutar codigo txt personalizado usar:")
        print("python iroptimizer.py archivo.bminor -O0")
        print("python iroptimizer.py archivo.bminor -O1")
        print("python iroptimizer.py archivo.bminor -O2")

        #-------------------------------------------------------
        # PRUEBAS INSTRUCCIONES O1
        #-------------------------------------------------------
        print("="*50)
        print("|PRUEBAS INSTRUCCIONES O1|".center(50, " "))
        print("="*50,"\n")

        # Prueba constraint folding ADDI O1
        print(">>> CONSTRAINT FOLDING\n")

        insts1 = [
            ("MOVI", 2, "R1"),
            ("MOVI", 3, "R2"),
            ("ADDI", "R1", "R2", "R3"),
            ("PRINTI", "R3"),
        ]
        print("O0 - Sin optimizar:")
        print(insts1,"")

        out1 = optimize_insts(insts1, level=1)
        print("O1 - Optimizado:")
        print(out1,"")
        print("-"*50,"\n")

        # Prueba Simplificación Algebráica O1
        print(">>> SIMPLIFICACIÓN ALGEBRÁICA\n")

        insts2 = [
            ("MOVI", 5, "R1"),
            ("MOVI", 0, "R2"),
            ("ADDI", "R1", "R2", "R3"),
            ("PRINTI", "R3")
        ]

        print("O0 - Sin optimizar:")
        print(insts2,"")

        out2 = optimize_insts(insts2, level=1)
        print("O1 - Optimizado:")
        print(out2,"")
        print("-"*50,"\n")        

        # Prueba comparaciones constantes O1
        print(">>> COMPARACIONES CONSTANTES\n")
        
        insts3 = [
            ("MOVI", 2, "R1"),
            ("MOVI", 5, "R2"),
            ("CMPI", ">", "R1", "R2", "R3")
        ]
        
        print("O0 - Sin optimizar:")
        print(insts3,"")

        out3 = optimize_insts(insts3, level=1)
        print("O1 - Optimizado:")
        print(out3,"")
        print("-"*50,"\n")

        # Prueba simplificación de ramas condicionales O1
        print(">>> SIMPLIFICACIÓN DE RAMAS CONDICIONALES\n")

        insts4 = [
            ("MOVI", 1, "R1"),
            ("CBRANCH", "R1", "Ltrue", "Lfalse")
        ]

        print("O0 - Sin optimizar:")
        print(insts4,"")

        out4 = optimize_insts(insts4, level=1)
        print("O1 - Optimizado:")
        print(out4,"")
        print("-"*50,"\n")  

        # Prueba Código Inalcanzable O1
        print(">>> CÓDIGO INALCANZABLE\n")

        insts5 = [
            ("BRANCH", "L1"),
            ("MOVI", 99, "R9"),
            ("PRINTI", "R9"),
            ("LABEL", "L1"),
            ("MOVI", 1, "R1")
        ]

        print("O0 - Sin optimizar:")
        print(insts5,"")

        out5 = optimize_insts(insts5, level=1)
        print("O1 - Optimizado:")
        print(out5,"")
        print("-"*50,"\n")  

        # Prueba Salto al siguiente label O1
        print(">>> SALTO AL SIGUIENTE LABEL\n")
        insts6 = [
            ("BRANCH", "L1"),
            ("LABEL", "L1")
        ]

        print("O0 - Sin optimizar:")
        print(insts6,"")

        out6 = optimize_insts(insts6, level=1)
        print("O1 - Optimizado:")
        print(out6,"")


        #-------------------------------------------------------
        # PRUEBAS O2
        #-------------------------------------------------------
        print("="*50)
        print("|PRUEBAS INSTRUCCIONES O2|".center(50, " "))
        print("="*50,"\n")

        # Prueba Eliminación de temportales muertos O2
        print(">>> ELIMINACIÓN DE TEMPORALES MUERTOS\n")
        
        insts7 = [
            ("MOVI", 2, "R1"),
            ("MOVI", 3, "R2"),
            ("ADDI", "R1", "R2", "R3"),
            ("MOVI", 99, "R4"),
            ("PRINTI", "R3"),
        ]
        print("O0 - Sin optimizar:")
        print(insts7,"")

        out7 = optimize_insts(insts7, level=2)
        print("O2 - Optimizado:")
        print(out7,"")
        print("-"*50,"\n")  


