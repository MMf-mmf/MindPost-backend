### Starting the application (based on docker-compose)
```shell
docker compose up --build   
```
### open a shell in the container
```shell
docker exec -it strawberry-fields-app python manage.py shell
```
### commands to create and run migrations and create superuser
```shell
docker exec -it strawberry-fields-app python manage.py makemigrations
docker exec -it strawberry-fields-app python manage.py migrate
docker exec -it strawberry-fields-app python manage.py createsuperuser
```


## Commands not directly related to the application

## to stop a local postgresql instance
```shell
brew services stop postgresql@16
```