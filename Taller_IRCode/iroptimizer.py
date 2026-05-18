from __future__ import annotations

from typing import Any, Optional

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

                # TODO 1:
                # Si a y b son constantes, evaluar la operación.
                # Reemplazar por MOVI o MOVF.
                # No optimizar división por cero.

                # TODO 2:
                # Aplicar reglas algebraicas simples.

                const.pop(dst, None)
                out.append(inst)
                continue

            if op in {"CMPI", "CMPF", "CMPB"} and len(inst) == 5:
                cmp_oper, a, b, dst = inst[1], inst[2], inst[3], inst[4]

                # TODO 3:
                # Si a y b son constantes, reemplazar por MOVI 1 o MOVI 0.

                const.pop(dst, None)
                out.append(inst)
                continue

            if op == "CBRANCH" and len(inst) == 4:
                test, true_label, false_label = inst[1], inst[2], inst[3]

                # TODO 4:
                # Si test es constante, reemplazar por BRANCH true_label o false_label.

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

            # TODO 5:
            # Si llega un LABEL, termina la zona inalcanzable.
            # Si estamos en zona inalcanzable, descartar la instrucción.
            # Si se ve BRANCH o RET, marcar unreachable = True.

            out.append(inst)

        return out

    def remove_branch_to_next_label(self, instructions: list[Instruction]) -> list[Instruction]:
        out: list[Instruction] = []
        i = 0

        while i < len(instructions):
            inst = instructions[i]

            # TODO 6:
            # Si inst es BRANCH Lx y la siguiente instrucción es LABEL Lx,
            # eliminar el BRANCH.

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

            # TODO 7:
            # Si dst no es None, dst no está en used y la instrucción es pura,
            # eliminarla.

            # TODO 8:
            # Actualizar used correctamente.

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