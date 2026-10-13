from main import app

print('API Routes:')
for route in app.routes:
    if hasattr(route, 'path') and '/api/v1/' in route.path:
        print(f'  {route.path}')
