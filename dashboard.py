
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError


load_dotenv()


def get_engine():
    """Create SQLAlchemy engine from DATABASE_URL."""

    url = os.getenv("DATABASE_URL")

    if not url:
        raise ValueError("DATABASE_URL is missing in .env file")

    return create_engine(url)


def store_report(engine):
    """Print store statistics, catalog and top customers."""

    with engine.connect() as conn:

        users_count = conn.execute(
            text("select count(*) from users")
        ).scalar_one()

        products_count = conn.execute(
            text("select count(*) from products")
        ).scalar_one()

        orders_count = conn.execute(
            text("select count(*) from orders")
        ).scalar_one()

        print("\n=== Store Dashboard ===")
        print(f"Users: {users_count} | Products: {products_count} | Orders: {orders_count}")

        # Product catalog
        products = conn.execute(
            text("""
                select name, price, stock
                from products
                order by name
            """)
        ).fetchall()

        print("\nCatalog:")

        for product in products:
            print(
                f"  {product.name:<15} "
                f"${product.price:>8.2f} "
                f"(stock: {product.stock})"
            )

        # Top 3 customers
        customers = conn.execute(
            text("""
                select
                    u.email,
                    sum(o.quantity) as total_items
                from users as u
                join orders as o
                    on u.id = o.user_id
                group by u.id, u.email
                order by total_items desc
                limit 3
            """)
        ).fetchall()

        print("\nTop customers:")

        for customer in customers:
            print(
                f"  {customer.email} - "
                f"{customer.total_items} items"
            )

        # Optional: low stock products
        low_stock = conn.execute(
            text("""
                select name, stock
                from products
                where stock < 10
                order by stock
            """)
        ).fetchall()

        print("\nLow stock products:")

        if low_stock:
            for product in low_stock:
                print(f"  {product.name}: {product.stock}")
        else:
            print("  No products with low stock.")


def add_product(engine, name, category, price, stock):
    """Insert a product and return its new ID."""

    with engine.begin() as conn:

        result = conn.execute(
            text("""
                insert into products (name, category, price, stock)
                values (:name, :category, :price, :stock)
                returning id
            """),
            {
                "name": name,
                "category": category,
                "price": price,
                "stock": stock
            }
        )

        product_id = result.scalar_one()

    return product_id


def place_order(engine, email, product_name, quantity):
    """Create an order and decrease stock in one transaction."""

    if quantity <= 0:
        raise ValueError("Quantity must be greater than zero.")

    with engine.begin() as conn:

        # Find user
        user = conn.execute(
            text("""
                select id
                from users
                where email = :email
            """),
            {"email": email}
        ).fetchone()

        if user is None:
            raise ValueError("User not found.")

        # Find product and lock its row
        product = conn.execute(
            text("""
                select id, stock
                from products
                where name = :product_name
                for update
            """),
            {"product_name": product_name}
        ).fetchone()

        if product is None:
            raise ValueError("Product not found.")

        if product.stock < quantity:
            raise ValueError(
                f"Not enough stock. Available: {product.stock}"
            )

        # Create order
        conn.execute(
            text("""
                insert into orders (user_id, product_id, quantity, status)
                values (:user_id, :product_id, :quantity, :status)
            """),
            {
                "user_id": user.id,
                "product_id": product.id,
                "quantity": quantity,
                "status": "pending"
            }
        )

        # Decrease product stock
        conn.execute(
            text("""
                update products
                set stock = stock - :quantity
                where id = :product_id
            """),
            {
                "quantity": quantity,
                "product_id": product.id
            }
        )

    print("\nOrder successfully created!")


def main():

    try:
        engine = get_engine()

        # Check database connection
        with engine.connect() as conn:
            conn.execute(text("select 1"))

        print("Database connection successful!")

        while True:

            store_report(engine)

            print("\n=== MENU ===")
            print("1. Add product")
            print("2. Place order")
            print("3. Exit")

            choice = input("\nChoose an option: ")

            try:
                if choice == "1":

                    name = input("Product name: ")
                    category = input("Category: ")
                    price = float(input("Price: "))
                    stock = int(input("Stock: "))

                    if price < 0 or stock < 0:
                        raise ValueError(
                            "Price and stock cannot be negative."
                        )

                    product_id = add_product(
                        engine,
                        name,
                        category,
                        price,
                        stock
                    )

                    print(f"\nProduct added! ID: {product_id}")

                elif choice == "2":

                    email = input("User email: ")
                    product_name = input("Product name: ")
                    quantity = int(input("Quantity: "))

                    place_order(
                        engine,
                        email,
                        product_name,
                        quantity
                    )

                elif choice == "3":

                    print("Goodbye!")
                    break

                else:
                    print("Invalid option.")

            except (ValueError, SQLAlchemyError) as error:
                print(f"\nOperation failed: {error}")

        engine.dispose()

    except (ValueError, SQLAlchemyError) as error:
        print(f"Database connection failed: {error}")


if __name__ == "__main__":
    main()
