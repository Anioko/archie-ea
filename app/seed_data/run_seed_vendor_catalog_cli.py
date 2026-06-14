import os

from app import create_app


def main():
    # Ensure dev seed flag is set before importing seed module
    os.environ["DEV_SEED_VENDOR_CATALOG"] = "1"
    app = create_app("development")
    with app.app_context():
        from app.seed_data.seed_vendor_catalogue import seed_vendor_catalogue

        seed_vendor_catalogue()
        print("Vendor catalogue seed executed (development only).")


if __name__ == "__main__":
    main()
