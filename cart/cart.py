from myapp.models import Product
from decimal import Decimal

class Cart():
    def __init__(self, request):
        self.session = request.session
        cart = request.session.get('cart')
        if 'cart' not in request.session:
            cart = self.session['cart'] = {}
        self.cart = cart

    def __len__(self):
        return sum(int(item['qty']) for item in self.cart.values())

    def __iter__(self):
        product_ids = self.cart.keys()
        products = Product.objects.filter(id__in=product_ids)
        cart = self.cart.copy()

        for product in products:
            cart[str(product.id)]['product'] = product

        for item in cart.keys():
            cart[item]['price'] = Decimal(cart[item]['price'])
            cart[item]['qty'] = Decimal(cart[item]['qty'])
            cart[item]['total'] = Decimal(cart[item]['price'] * cart[item]['qty'])
            yield cart[item]

    def get_total_price(self):
        cart = self.cart.copy()
        total_price = Decimal(0)
        for item in cart.keys():
            price = Decimal(cart[item]['price'])
            quantity = Decimal(cart[item]['qty'])
            item_price = price * quantity
            total_price += item_price
        return total_price


    def add(self, product_id, product_quantity):
        product = Product.objects.get(pk=product_id)
        if product_id in self.cart:
            self.cart[product_id]['qty'] = product_quantity
        else:
            self.cart[product_id] = {
                'price': str(product.price),
                'qty': product_quantity
            }
        print(f'Cart pID {product_id}')
        self.session.modified = True

    def update(self, product_id, product_quantity):
        product_id = str(product_id)
        if product_id in self.cart:
            self.cart[product_id]['qty'] = product_quantity
            self.session.modified = True

    def delete(self, product_id):
        product_id = str(product_id)
        if product_id in self.cart:
            del self.cart[product_id]
            self.session.modified = True

