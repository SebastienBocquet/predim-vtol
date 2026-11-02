# Consignes projet

## Scripts sous Windows
Tout script qui évalue PredimRC via `open_backend` (cache HDF5 GEMSEO) doit mettre son
code dans une fonction appelée sous `if __name__ == "__main__":`. Le cache HDF5 démarre un
`multiprocessing.Manager` : sous Windows (spawn), le process enfant réimporte le script, et
un code au niveau module le relance, d'où une erreur de bootstrap ou un blocage.
