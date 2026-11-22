# Consignes projet

## Scripts sous Windows
Jusqu'à la 0.3, le cache HDF5 GEMSEO de `open_backend` démarrait un
`multiprocessing.Manager` : un script qui évaluait PredimRC devait mettre son code sous
`if __name__ == "__main__":` (sous Windows, spawn, le process enfant réimporte le script).
Le cache est désormais un dossier `joblib.Memory` (INC4-002) qui ne démarre aucun process :
cette contrainte ne vaut plus que pour un script qui lance lui-même des process
(`multiprocessing`, `joblib.Parallel`, `ProcessPoolExecutor`).
