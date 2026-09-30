# VoltPC — Django E-Commerce Platform
[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-6.1-green)](https://www.djangoproject.com/)
[![PostgreSQL](https://img.shields.io/badge/Postgresql-18.6-green)](https://www.postgresql.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](./LICENSE)
<img width="1767" height="865" alt="Django-Ecommerece-Ali-Rahmanianaraki" src="https://github.com/user-attachments/assets/cfe112fc-8338-4b8f-ab4d-1d2ca26b404d" />


A full-featured e-commerce web application built with **Django 6.1**, designed as a computer parts store. It includes product browsing, cart management, user accounts, order placement, wishlists, email verification, password reset, and a fully styled responsive interface powered by **Tailwind CSS**.

This project was built as a hands-on learning exercise to explore real-world Django patterns: session-based carts, custom user flows, service-layer logic, AJAX interactions, and template inheritance.

---

## ✨ Features

### 🛍️ Product Browsing
- **Product listing** — grid view of all products with images, prices, and stock status
- **Product detail page** — large images, description, tags, stock info, and add-to-cart controls
- **Tag-based browsing** — click any tag to see all products with that tag
- **Product images** — multiple images per product with thumbnail display
- **Search & filter ready** — the data model supports category/tag filtering

### 🛒 Shopping Cart
- **Session-based cart** — persists across page navigation
- **Add / update / remove items** — all via AJAX (no page reloads)
- **Cart badge** — live item count in the header, updated on every action
- **Quantity stepper** — increment / decrement with input validation
- **Cart overview page** — full item list with per-item totals and grand total

### 👤 User Accounts
- **Registration** with email verification
- **Login / logout** with session preservation (cart survives login)
- **Profile page** — view account info and shipping address
- **Profile editing** — update username, email, name
- **Password reset** — full flow with email link and token validation
- **Email change verification** — changing email requires re-verification
- **Shipping addresses** — one address per user, editable from profile

### ❤️ Wishlist
- **Add to wishlist** from product detail pages (AJAX)
- **Remove from wishlist** via AJAX on the wishlist page
- **Wishlist overview** — grid view of saved products
- **Empty state** — friendly message when the wishlist is empty
- **Service-layer logic** — `WishlistService` handles add/remove/clear cleanly

### 📦 Orders
- **Checkout review page** — read-only summary of address + cart
- **Place order** — creates `Order` and `OrderItem` records
- **Order success / failure pages**
- **JSON-based AJAX** responses with proper status codes

### 🎨 UI / UX
- **Tailwind CSS** for all styling
- **Responsive design** — works on mobile, tablet, and desktop
- **Gradient backgrounds**, **frosted cards**, and **hover animations**
- **Toast notifications** for AJAX feedback
- **Empty states** everywhere — no blank pages
- **Consistent design language** across all pages

---

## 🧱 Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Django 6.1 |
| **Language** | Python 3.12 |
| **Database** | SQLite (development) |
| **Frontend** | Tailwind CSS (CDN), jQuery 4 |
| **Email** | SMTP via Gmail (django.core.mail) |
| **Auth** | Django's built-in `User` model + custom flows |
| **Media** | Django `MEDIA_ROOT` / `MEDIA_URL` |

---

## 📁 Project Structure

```
Ecommerce/
├── mysite/                 # Project settings & root URLs
│   ├── settings.py
│   ├── urls.py
│   └── ...
│
├── myapp/                  # Core app: products, tags, images
│   ├── models.py           # Product, Tag, ProductImage
│   ├── views.py            # index, detail, tag
│   └── ...
│
├── cart/                   # Session-based cart
│   ├── cart.py             # Cart class (session-backed)
│   ├── context_processor.py
│   ├── views.py            # add, update, delete, overview
│   └── ...
│
├── users/                  # Auth, profile, addresses
│   ├── models.py           # Address
│   ├── forms.py            # Register, Login, Profile, Address
│   ├── views.py            # register, login, logout, profile, ...
│   ├── token.py            # Custom email verification token
│   └── ...
│
├── orders/                 # Checkout & orders
│   ├── models.py           # Order, OrderItem
│   ├── views.py            # checkout, place_order
│   └── ...
│
├── wishlists/              # Wishlist
│   ├── models.py           # Wishlist, WishlistItems
│   ├── wishlist.py         # WishlistService
│   ├── views.py            # add, remove, overview
│   └── ...
│
├── media/                  # Uploaded product images
├── db.sqlite3
└── manage.py
```

---

## ⚙️ Setup & Installation

### 1. Clone the repository
```bash
git clone https://github.com/alirahmanianaraki/django-ecommerce.git
cd django-ecommerce
```

### 2. Create a virtual environment
```bash
python -m venv env

# Windows
env\Scripts\activate

# macOS / Linux
source env/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment variables
Create a `.env` file in the project root:

```env
SECRET_KEY=your-secret-key
DEBUG=True

# Email (SMTP)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_USERNAME=your-email@gmail.com
EMAIL_PASSWORD=your-app-password
```

> **Note**: For Gmail, you must use an **App Password**, not your regular password. See the [Google support page](https://support.google.com/accounts/answer/185833) for details.

### 5. Apply migrations
```bash
python manage.py migrate
```

### 6. Create a superuser
```bash
python manage.py createsuperuser
```

### 7. Run the development server
```bash
python manage.py runserver
```

Visit `http://127.0.0.1:8000/` to browse the store, or `http://127.0.0.1:8000/admin/` for the Django admin.

---

## 🔑 Core Concepts & Design Decisions

### Session-Based Cart
The cart is stored in `request.session['cart']` — a nested dictionary keyed by product ID:

```python
{
    '1': {'price': '59.00', 'qty': 2},
    '4': {'price': '187.99', 'qty': 1}
}
```

The `Cart` class wraps this with a Pythonic interface:
- `__len__` — total quantity
- `__iter__` — yields enriched items with `product`, `price`, `qty`, `total`
- `add`, `update`, `delete` — modify the session and mark it modified

### Context Processor
`cart.context_processor.cart` injects the cart into every template, so the header badge works everywhere without passing it from each view.

### Service Layer
`WishlistService` encapsulates wishlist operations — `add`, `remove`, `clear` — so views stay thin and logic lives in one place.

### Email Verification Token
A custom `EmailVerificationTokenGenerator` (extending Django's `PasswordResetTokenGenerator`) generates tokens based on `user.pk`, a timestamp, and `user.is_active`. The token is invalidated once the user activates, preventing reuse.

### AJAX Everywhere
Cart, wishlist, and order operations use AJAX with JSON responses. Failures return proper HTTP status codes (400, 401) so the frontend can react — no silent redirects.

### Checkout as Review
The checkout page is a **read-only review** of the shipping address and cart items — users edit elsewhere (cart page, profile). This reduces mistakes and simplifies the flow.

---

## 🔒 Security Notes

- **CSRF protection** enabled on all forms and AJAX requests
- **Password hashing** via Django's `set_password`
- **Email verification** required before login
- **Password reset** uses time-limited, single-use tokens
- **Session-based cart** is tied to the browser session

For production:
- Set `DEBUG = False`
- Configure `ALLOWED_HOSTS`
- Use **PostgreSQL** or another production database
- Use **HTTPS**
- Use a real email backend (not console)
- Serve static/media files via a web server (Nginx, S3, etc.)

---

## 🤝 Contributing

This is a personal learning project, but contributions and suggestions are welcome. Feel free to open an issue or submit a pull request.

---

## 📄 License

This project is open source and available under the **MIT License**.

---

## 🙏 Acknowledgements

- Built as a hands-on project to learn Django's real-world patterns
- Inspired by the Django Masterclass "Build 9 Real World Django Projects" course
- Design language inspired by modern e-commerce sites like Newegg and Micro Center

---

## 📬 Contact

**Ali Rahmanianaraki** — [alirahmanianaraki99@yahoo.com](mailto:your@email.com)

Project Link: https://github.com/alirahmanianaraki/django-ecommerce
