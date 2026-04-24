from os import system, path

if __name__ == "__main__":
    testlist = [f"typechecker/good{i}.bminor" for i in range(10)]
    testlist += [f"typechecker/bad{i}.bminor" for i in range(10)]
    for test in testlist:
        print(f"para {path.basename(test)}:".upper())
        system(f"python checker.py {test}")
        print() # -> newline