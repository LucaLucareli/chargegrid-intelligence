def busca_sequencial(sessoes: list, id_procurado: str):
    for i in range(len(sessoes)):
        if sessoes[i].id_sessao == id_procurado:
            return i
    return -1


def bubble_sort(sessoes: list, criterio: str):
    n = len(sessoes)
    for i in range(n):
        for j in range(n - 1 - i):
            swap = False
            
            if criterio == '1': 
                if sessoes[j].id > sessoes[j + 1].id:
                    swap = True
            elif criterio == '2': 
                if sessoes[j].energia > sessoes[j + 1].energia:
                    swap = True
            elif criterio == '3': 
                if sessoes[j].custo > sessoes[j + 1].custo:
                    swap = True
            elif criterio == '4': 
                if sessoes[j].tempo > sessoes[j + 1].tempo:
                    swap = True

            if swap:
                sessoes[j], sessoes[j + 1] = sessoes[j + 1], sessoes[j]
