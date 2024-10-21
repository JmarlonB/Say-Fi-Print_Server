import shelve

class SORM:
    def __init__(self):
        self.db = shelve.open('amigos.db')
        if 'indices' not in self.db:
            self.db['indices'] = {}

    def agregar_amigo(self, id, nombre):
        indices = self.db['indices']
        if str(id) in self.db or nombre in indices:
            print('Ya existe un amigo con ese ID o nombre')
            return
        self.db[str(id)] = nombre
        indices[nombre] = str(id)
        self.db['indices'] = indices

    def modificar_amigo(self, id, nuevo_nombre):
        if str(id) not in self.db:
            print('No existe un amigo con ese ID')
            return
        nombre_antiguo = self.db[str(id)]
        indices = self.db['indices']
        del indices[nombre_antiguo]
        self.db[str(id)] = nuevo_nombre
        indices[nuevo_nombre] = str(id)
        self.db['indices'] = indices

    def eliminar_amigo(self, id):
        if str(id) not in self.db:
            print('No existe un amigo con ese ID')
            return
        nombre = self.db[str(id)]
        indices = self.db['indices']
        del indices[nombre]
        del self.db[str(id)]
        self.db['indices'] = indices

    def buscar_amigo(self, id=None, nombre=None):
        if id:
            if str(id) not in self.db:
                print('No existe un amigo con ese ID')
                return
            nombre = self.db[str(id)]
            print(f'ID: {id}, Nombre: {nombre}')
            return nombre
        elif nombre:
            indices = self.db['indices']
            if nombre not in indices:
                print('No existe un amigo con ese nombre')
                return 
            id = indices[nombre]
            print(f'ID: {id}, Nombre: {nombre}')
            return id
        else:
            print('Debe especificar un ID o un nombre para buscar')
            return

    def listar_amigos(self):
        for id, nombre in self.db.items():
            if id != 'indices':
                print(f'ID: {id}, Nombre: {nombre}')
                return (f'ID: {id}, Nombre: {nombre}')

    def __del__(self):
        self.db.close()

if __name__ == '__main__':
    svorm=SORM()
    #svorm.agregar_amigo("54341156407634","Nico")
    #svorm.eliminar_amigo("5493416407634")
    svorm.listar_amigos()
    svorm.__del__()
