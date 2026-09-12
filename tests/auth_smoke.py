from fastapi.testclient import TestClient
from app.main import app

with TestClient(app) as client:
    client.post('/users', json={'name': 'Auth User', 'email': 'auth@example.com', 'password': 'secret123'})
    client.post('/users', json={'name': 'Other User', 'email': 'other@example.com', 'password': 'secret123'})
    user = client.post('/users', json={'name': 'Owner', 'email': 'owner@example.com', 'password': 'secret123'}).json()
    product = client.post('/products', json={'name': 'Wireless Mouse', 'price': '20.00', 'stock_qty': 5}).json()
    expensive = client.post('/products', json={'name': 'Gaming Keyboard', 'price': '80.00', 'stock_qty': 5}).json()

    assert client.get('/cart', params={'user_id': user['id']}).status_code == 401
    login = client.post('/auth/login', json={'email': 'owner@example.com', 'password': 'secret123'})
    assert login.status_code == 200, login.text
    token = login.json()['access_token']
    assert login.json()['token_type'] == 'bearer'
    headers = {'Authorization': f'Bearer {token}'}

    assert client.get('/users', headers=headers).status_code == 200
    assert client.get('/users/' + user['id'], headers=headers).status_code == 200
    assert client.get('/users/' + user['id'], headers={'Authorization': 'Bearer invalid'}).status_code == 401

    products = client.get('/products', params={'name': 'mouse', 'min_price': 10, 'max_price': 30, 'sort': 'price_desc'})
    assert products.status_code == 200 and len(products.json()) == 1

    first_image = client.post(f"/products/{product['id']}/images", json={'image_url': 'https://cdn.example.com/mouse-front.jpg'})
    assert first_image.status_code == 201 and first_image.json()['is_primary'] is True
    second_image = client.post(f"/products/{product['id']}/images", json={'image_url': 'https://cdn.example.com/mouse-side.jpg', 'is_primary': True})
    assert second_image.status_code == 201 and second_image.json()['is_primary'] is True
    images = client.get(f"/products/{product['id']}/images")
    assert images.status_code == 200 and len(images.json()) == 2 and sum(i['is_primary'] for i in images.json()) == 1

    address = client.post('/addresses', headers=headers, json={'label': 'Home', 'address_line': '1 Main Road', 'city': 'Delhi', 'state': 'Delhi', 'postal_code': '110001', 'is_default': True})
    assert address.status_code == 201 and address.json()['is_default'] is True
    address_id = address.json()['id']
    second_address = client.post('/addresses', headers=headers, json={'label': 'Office', 'address_line': '2 Work Road', 'city': 'Delhi', 'state': 'Delhi', 'postal_code': '110002'})
    assert second_address.status_code == 201 and second_address.json()['is_default'] is False

    cart = client.post('/cart', headers=headers, json={'user_id': user['id'], 'product_id': product['id'], 'quantity': 1})
    assert cart.status_code == 201, cart.text
    assert client.get('/cart', headers=headers, params={'user_id': user['id']}).status_code == 200

    other = client.post('/auth/login', json={'email': 'other@example.com', 'password': 'secret123'}).json()['access_token']
    assert client.get('/cart', headers={'Authorization': f'Bearer {other}'}, params={'user_id': user['id']}).status_code == 403
    order = client.post('/orders', headers=headers, json={'user_id': user['id'], 'address_id': address_id, 'items': [{'product_id': product['id'], 'quantity': 1}]})
    assert order.status_code == 201 and order.json()['address_id'] == address_id

    assert client.post('/auth/login', json={'email': 'owner@example.com', 'password': 'wrong'}).status_code == 401

print('auth validation passed')
