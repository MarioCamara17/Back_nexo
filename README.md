# BinMap API

## Descripción
BinMap API es el servicio backend que impulsa una aplicación móvil diseñada como un mapa interactivo para las estaciones del Tren Maya. Este backend, desarrollado con Django y Django REST Framework, proporciona los endpoints necesarios para la autenticación de usuarios y la gestión de cuentas, así como para la obtención de datos sobre puntos de interés y rutas turísticas en las estaciones del Tren Maya. El objetivo es enriquecer la experiencia del turista y promover el turismo en la región mediante un acceso eficiente y seguro a la información turística.

## Requisitos
- Python 3.12
- pip
- pipenv

## Instalación

### 1. Clonar el repositorio
```bash
git clone https://github.com/C4rlosMH/back_binmap.git
```

### 2. Configurar el entorno virtual e instalar dependencias
```bash
pipenv install
```

### 3. Generar una clave secreta para Django

Para generar una clave secreta segura para Django, visita el siguiente enlace:

[Django Secret Key Generator](https://miniwebtool.com/es/django-secret-key-generator/)

Esta herramienta generará una clave secreta aleatoria y segura que podrás usar en tu archivo `.env`.

### 4. Configurar variables de entorno
Crea un archivo `.env` en la raíz del proyecto basado en el archivo `env-example.txt`:
```bash
cp env-example.txt .env
```

El archivo `.env` debe contener:
```env
SECRET_KEY=Tu clave secreta de django
DEBUG=True
ALLOWED_HOSTS=https://back-nexo.onrender.com
```

Reemplaza "Tu clave secreta de django" con la clave generada en el paso anterior.

### 5. Activar el entorno virtual
```bash
pipenv shell
```

### 6. Aplicar migraciones
```bash
python manage.py makemigrations
python manage.py migrate
```

### 7. Crear un superusuario (opcional)
```bash
python manage.py createsuperuser
```

### 8. Iniciar el servidor de desarrollo
```bash
python manage.py runserver
```

## Uso de la API

La API proporciona los siguientes endpoints:

### Autenticación
- `POST /api/v1/auth/login/` - Iniciar sesión
- `POST /api/v1/auth/logout/` - Cerrar sesión
- `POST /api/v1/auth/signup/` - Registrar nuevo usuario
- `GET /api/v1/auth/user-detail/` - Obtener detalles del usuario actual
- `POST /api/v1/auth/reset/` - Solicitar restablecimiento de contraseña

### Recursos
- `GET /api/v1/states/` - Listar estados
- `GET /api/v1/municipalities/` - Listar municipios
- `GET /api/v1/categories/` - Listar categorías de lugares
- `GET /api/v1/places/` - Listar lugares de interés
- `GET /api/v1/favorites/` - Gestionar lugares favoritos del usuario
- `GET /api/v1/routes/` - Listar rutas turísticas
- `GET /api/v1/municipality-routes/` - Listar rutas por municipio

Todos los endpoints utilizan el prefijo `/api/v1/` y siguen los estándares REST para las operaciones CRUD.

## Panel de administración
El panel de administración de Django está disponible en `/admin/`. Necesitarás haber creado un superusuario para acceder.

## Desarrollo
Para contribuir al proyecto, sigue estas pautas:

1. Crea una rama para tu función: `git checkout -b nombre-feature`
2. Realiza tus cambios y haz commit: `git commit -m 'Descripción del cambio'`
3. Envía tus cambios: `git push origin nombre-feature`
4. Abre un Pull Request
