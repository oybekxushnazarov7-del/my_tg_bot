import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import init_db, add_faq, list_faqs, get_connection

def seed_database():
    print("Initializing database...")
    init_db()
    
    existing = list_faqs()
    if len(existing) > 0:
        print(f"Database already contains {len(existing)} FAQ entries. Clearing existing for a fresh seed...")
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM faqs")
        conn.commit()
        conn.close()

    print("Seeding sample FAQ data for 'EcoGlow Boutique' (Eco-friendly skincare & organic products)...")
    
    sample_faqs = [
        {
            "question": "What are your working/opening hours?",
            "answer": "We are open Monday to Friday from 9:00 AM to 7:00 PM, and Saturday from 10:00 AM to 5:00 PM. We are closed on Sundays."
        },
        {
            "question": "Where is your store located? Do you have a physical shop?",
            "answer": "Yes, our flagship physical store is located at 123 Green Valley Street, Suite A, Austin, Texas. You can find us on Google Maps by searching for 'EcoGlow Boutique'."
        },
        {
            "question": "What is your delivery policy? How long does shipping take?",
            "answer": "We ship nationwide! Standard shipping takes 3-5 business days and is free for orders over $50. Express shipping takes 1-2 business days and costs $9.99. Orders are shipped within 24 hours of placement."
        },
        {
            "question": "Can I return or exchange a product?",
            "answer": "We offer a 30-day money-back guarantee on all unopened and unused products. If you receive a damaged item or are unsatisfied, please contact our support to initiate a return or exchange."
        },
        {
            "question": "Are your skincare products suitable for sensitive skin?",
            "answer": "Yes! All EcoGlow skincare products are dermatologist-tested, hypoallergenic, 100% organic, and specifically formulated for sensitive skin. They contain no synthetic fragrances or paraben preservatives."
        },
        {
            "question": "Do you offer international shipping?",
            "answer": "Currently, we only ship within the United States and Canada. We plan to expand to Europe and other regions by the end of this year."
        },
        {
            "question": "How can I track my order?",
            "answer": "Once your order is shipped, you will receive a tracking link via email or SMS. You can also type /track in this bot or check the 'Track Order' option on our website."
        },
        {
            "question": "What payment methods do you accept?",
            "answer": "We accept all major credit cards (Visa, MasterCard, American Express), PayPal, Apple Pay, and Google Pay. Cash on delivery is only available for in-store pickup orders."
        },
        {
            "question": "Are your products cruelty-free and vegan?",
            "answer": "Yes, 100%. We are certified cruelty-free by Leaping Bunny, and all our formulations are completely vegan, using only plant-based ingredients."
        },
        {
            "question": "Do you offer gift wrapping services?",
            "answer": "Yes, we offer premium, eco-friendly gift wrapping with recycled materials. You can add a gift message and request wrapping at checkout for an additional fee of $3.50."
        },
        {
            "question": "How can I contact a human operator or support manager?",
            "answer": "You can connect with a live operator at any time by pressing the 'Talk to Human' button or typing the command /handoff. One of our support managers will get back to you shortly."
        }
    ]

    for faq in sample_faqs:
        faq_id = add_faq(faq["question"], faq["answer"])
        print(f"Added FAQ #{faq_id}: '{faq['question'][:30]}...'")

    print("\nDatabase seeded successfully!")

if __name__ == "__main__":
    seed_database()
