import sqlite3
import datetime

# Helper function to connect to the database:
def connect_to_database():
    conn = sqlite3.connect('library.db')
    conn.row_factory = sqlite3.Row # This allows accessing attributes by name
    return conn

# 1. Find an item in the library:
def find_item(keyword):
    conn = connect_to_database()
    cursor = conn.cursor()

    cursor.execute('''
    SELECT *
    FROM LibraryItems
    WHERE 
        Title LIKE ? OR Author LIKE ? OR ItemType LIKE ?
    ''', (f'%{keyword}%', f'%{keyword}%', f'%{keyword}%'))

    results = cursor.fetchall()
    conn.close()

    return results

# Display search results in a neatly formatted way:
def display_item_results(items):
    if not items:
        print("No items found matching your search criteria.")
        return

    print("\n{:<5} {:<30} {:<20} {:<15} {:<15} {:<20}".format("ID", "Title", "Author", "Type", "Status", "Location"))
    print("-" * 105)

    for item in items:
        print("{:<5} {:<30} {:<20} {:<15} {:<15} {:<20}".format(
            item['ItemID'],
            item['Title'][:28] + ".." if len(item['Title']) > 30 else item['Title'],
            item['Author'][:18] + ".." if item['Author'] and len(item['Author']) > 20 else (item['Author'] or "N/A"),
            item['ItemType'],
            item['AvailabilityStatus'],
            item['Location'][:18] + ".." if len(item['Location']) > 20 else item['Location']))



# 2. Borrow an item from the library:
def borrow_item(user_id, item_id):
    conn = connect_to_database()
    cursor = conn.cursor()

    # Check if item exists and is still available:
    cursor.execute('''
    SELECT Title, AvailabilityStatus
    FROM LibraryItems
    WHERE ItemID = ?
    ''', (item_id,))

    item = cursor.fetchone()

    if not item:
        conn.close()
        return False, "Item not found."

    if item['AvailabilityStatus'] != 'Available':
        conn.close()
        return False, f"Item '{item['Title']}' is not available for borrowing. Current status: {item['AvailabilityStatus']}"

    # Check if user exists and is not suspended:
    cursor.execute('''
    SELECT FullName, AccountStatus
    FROM Users
    WHERE UserID = ?
    ''', (user_id,))

    user = cursor.fetchone()

    if not user:
        conn.close()
        return False, "User not found."

    if user['AccountStatus'] == 'Suspended':
        conn.close()
        return False, f"User '{user[FullName]}' is suspended and cannot borrow items."

    # Check how many items the user has currently borrowed:
    cursor.execute('''
    SELECT COUNT(*) as borrowed_count
    FROM BorrowingTransactions
    WHERE UserID = ? AND ReturnDate IS NULL
    ''', (user_id,))

    result = cursor.fetchone()
    borrowed_count = result['borrowed_count']

    if borrowed_count >= 5:
        conn.close()
        return False, f"You have already borrowed 5 items. Please return some items before borrowing more."

    # Create new borrowing transaction:
    borrow_date = datetime.date.today()
    due_date = borrow_date + datetime.timedelta(days=14)
    try:
        cursor.execute('''
        INSERT INTO BorrowingTransactions (UserID, ItemID, BorrowDate, DueDate, OverdueStatus, FineAmount)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, item_id, borrow_date.strftime("%Y-%m-%d"), due_date.strftime("%Y-%m-%d"), 'No', 0.00))

        transaction_id = cursor.lastrowid
        
        conn.commit()
        conn.close()

        return True, f"Item '{item['Title']}' has been borrowed by {user['FullName']} until {due_date.strftime('%Y-%m-%d')} (Transaction ID: {transaction_id})."
        
    except sqlite3.Error as e:
        conn.rollback()
        conn.close()
        return False, f"Error borrowing item: {e}"



# 3. Return a borrowed item:
def return_item(transaction_id):
    conn = connect_to_database()
    cursor = conn.cursor()

    # Check if the transaction exists and the item hasn't been returned already:
    cursor.execute('''
    SELECT BT.TransactionID, BT.ReturnDate, BT.DueDate, U.FullName, LI.Title
    FROM 
        BorrowingTransactions BT 
    JOIN
        Users U ON BT.UserID = U.UserID
    JOIN
        LibraryItems LI ON BT.ItemID = LI.ItemID
    WHERE BT.TransactionID = ?
    ''', (transaction_id,))

    transaction = cursor.fetchone()

    if not transaction:
        conn.close()
        return False, "Transaction not found."

    if transaction['ReturnDate'] is not None:
        conn.close()
        return False, f"Item '{transaction['Title']}' has already been returned."

    return_date = datetime.date.today()

    # Update transaction with the return date
    try:
        cursor.execute('''
        UPDATE BorrowingTransactions
        SET ReturnDate = ?
        WHERE TransactionID = ?
        ''', (return_date.strftime("%Y-%m-%d"), transaction_id))

        # Check if the item was overdue
        due_date = datetime.datetime.strptime(transaction['DueDate'], "%Y-%m-%d").date()
        is_overdue = return_date > due_date
        fine_message = ""

        if is_overdue:
            days_overdue = (return_date - due_date).days
            fine_amount = days_overdue * 1 # 50 cents per day overdue

            # Check if a fine was created by the trigger
            cursor.execute('''
            SELECT FineID, AmountDue
            FROM Fines
            WHERE TransactionID = ?
            ''', (transaction_id,))

            fine = cursor.fetchone()
            if fine:
                fine_message = f"A fine of ${fine['AmountDue']:.2f} has been issued (FineID: {fine['FineID']})."

        conn.commit()
        conn.close()

        return True, f"Item '{transaction['Title']}' has been successfully returned by {transaction['FullName']}.{fine_message}"
    except sqlite3.Error as e:
        conn.rollback()
        conn.close()
        return False, f"Error returning item: {e}"



# 4. Donate an item to the library
def donate_item(title, author, item_type, publication_year, isbn=None, publisher=None):
    conn = connect_to_database()
    cursor = conn.cursor()

    try:
        cursor.execute('''
        INSERT INTO LibraryItems (Title, Author, ItemType, PublicationYear, ISBN, Publisher, AvailabilityStatus, Location)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (title, author, item_type, publication_year, isbn, publisher, 'Available', 'Processing Area'))

        item_id = cursor.lastrowid

        conn.commit()
        conn.close()

        return True, f"Thank you for your donation! Item '{title}' has been added to the library (ItemID: {item_id})."
        
    except sqlite3.Error as e:
        conn.rollback()
        conn.close()
        return False, f"Error adding donated item: {e}"
        


# 5. Find an event in the library:
def find_events(keyword=None, audience=None, future_only=True):
    conn = connect_to_database()
    cursor = conn.cursor()

    query = '''
    SELECT EventID, EventName, EventDate, EventDescription, TargetAudience, Location
    FROM Events
    '''

    params = []

    if keyword:
        query += " AND (EventName LIKE ? OR EventDescription LIKE ?)"
        params.extend([f'%{keyword}%', f'%{keyword}%'])

    if audience:
        query += " AND (TargetAudience = ? OR TargetAudience = 'Open to All')"
        params.append(audience)

    if future_only:
        query += " AND EventDate >= date('now')"

    query += " ORDER BY EventDate"

    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()

    return results

# Helper function to neatly display the results for finding an event:
def display_event_results(events):
    if not events:
        print("No events found matching your search criteria.")
        return

    print("\n{:<5} {:<30} {:<12} {:<12} {:<30}".format(
        "ID", "Event Name", "Date", "Audience", "Location"))
    print("-" * 90)

    for event in events:
        event_date = datetime.datetime.strptime(event['EventDate'], "%Y-%m-%d").date()
        print("\n{:<5} {:<30} {:<12} {:<12} {:<30}".format(
            event['EventID'],
            event['EventName'][:28] + ".." if len(event['EventName']) > 30 else event['EventName'],
            event_date.strftime("%Y-%m-%d"),
            event['TargetAudience'],
            event['Location'][:28] + ".." if len(event['Location']) > 30 else event['Location']))


# 6. Register for an event in the library:
def register_for_event(user_id, event_id):
    conn = connect_to_database()
    cursor = conn.cursor()

    # Check if the event exists and hasn't happened yet:
    cursor.execute('''
    SELECT EventName, EventDate, TargetAudience
    FROM Events
    WHERE EventID = ?
    ''', (event_id,))

    event = cursor.fetchone()

    if not event:
        conn.close()
        return False, "Event not found."
        
    event_date = datetime.datetime.strptime(event['EventDate'], "%Y-%m-%d").date()
    if event_date < datetime.date.today():
        conn.close()
        return False, f"Event '{event['EventName']}' has already taken place on {event_date.strftime('%Y-%m-%d')}."

    # Check if user exists and is able to register
    cursor.execute('''
    SELECT FullName, MembershipType, AccountStatus
    FROM Users
    WHERE UserID = ?
    ''', (user_id,))

    user = cursor.fetchone()

    if not user:
        conn.close()
        return False, "User not found."

    if user['AccountStatus'] == 'Suspended':
        conn.close()
        return False, f"User '{user['FullName']}' has a suspended account."

    # Check if audience restrictions apply:
    if event['TargetAudience'] not in ['Open to All', user['MembershipType']]:
        if event['TargetAudience'] == 'Children' and user['MembershipType'] != 'Child':
            conn.close()
            return False, f"Event '{event['EventName']}' is for children only."
        elif event['TargetAudience'] == 'Adults' and user['MembershipType'] not in ['Regular', 'Student', 'Senior']:
            conn.close()
            return False, f"Event '{event['EventName']}' is for adults only."
        elif event['TargetAudience'] == 'Seniors' and user['MembershipType'] != 'Senior':
            conn.close()
            return False, f"Event '{event['EventName']}' is for seniors only."

    # Check if user is already registered:
    cursor.execute('''
    SELECT AttendanceID
    FROM EventAttendance
    WHERE EventID = ? and UserID = ?
    ''', (event_id, user_id))

    if cursor.fetchone():
        conn.close()
        return False, f"User '{user['FullName']}' is already registered for event '{event['EventName']}'."

    # Register user for the event:
    try:
        cursor.execute('''
        INSERT INTO EventAttendance (EventID, UserID)
        VALUES (?, ?)
        ''', (event_id, user_id))

        conn.commit()
        conn.close()

        return True, f"User '{user['FullName']}' has been successfully registered for event '{event['EventName']}'."
        
    except sqlite3.Error as e:
        conn.rollback()
        conn.close()
        return False, f"Error registering for event: {e}"



# 7. Volunteer for the library:
def volunteer_for_library(full_name, email, phone_number, position, availability):
    conn = connect_to_database()
    cursor = conn.cursor()

    # Check if email already exists in Personnel table
    cursor.execute('''
    SELECT Email FROM Personnel WHERE Email = ?
    ''', (email,))

    if cursor.fetchone():
        conn.close()
        return False, f"A person with email '{email}' is already in our records."

    # Add volunteer to Personnel table:
    try:
        cursor.execute('''
        INSERT INTO Personnel (FullName, Position, Email, PhoneNumber, WorkSchedule)
        VALUES (?, ?, ?, ?, ?)
        ''', (full_name, position, email, phone_number, availability))

        staff_id = cursor.lastrowid

        conn.commit()
        conn.close()

        return True, f"Thank you, {full_name}! Your volunteer application has been processed. Your staff ID is {staff_id}."
        
    except sqlite3.Error as e:
        conn.rollback()
        conn.close()
        return False, f"Error processing volunteer application: {e}"



# 8. Ask for help from a librarian:
def ask_for_help(user_id, question_topic, question_details):
    conn = connect_to_database()
    cursor = conn.cursor()

    # Check if user exists:
    cursor.execute('''
    SELECT FullName FROM Users WHERE UserID = ?
    ''', (user_id,))

    user = cursor.fetchone()

    if not user:
        conn.close()
        return False, "User not found."

    # Find which librarian to ask the question to:
    position_keyword = "Librarian"
    if question_topic.lower() in ["computer", "technology", "internet", "digital", "WIFI", "tech"]:
        position_keyword = "IT"
    elif question_topic.lower() in ["event", "program", "workshop", "club"]:
        position_keyword = "Events"
    elif question_topic.lower() in ["children", "kids", "youth"]:
        position_keyword = "Children"
    elif question_topic.lower() in ["lost", "found", "missing", "danger", "threat", "security"]:
        position_keyword = "Security"

    cursor.execute('''
    SELECT StaffID, FullName, Email, Position
    FROM Personnel
    WHERE Position LIKE ?
    ORDER BY RANDOM() LIMIT 1
    ''', (f'%{position_keyword}%',))

    librarian = cursor.fetchone()

    # If no specialized librarian, then get a random one:
    if not librarian:
        cursor.execute('''
        SELECT StaffID, FullName, Email, Position
        FROM Personnel
        WHERE Position LIKE '%Librarian%'
        ORDER BY RANDOM() LIMIT 1
        ''')

        librarian = cursor.fetchone()

    conn.close()

    if not librarian:
        return False, "No librarians available at the moment. Please try again later."

    # Format response message:
    response = (f"Thank you for your question, {user['FullName']}! "
                f"Your request about '{question_topic}' has been directed to {librarian['FullName']} ({librarian['Position']}). "
                f"They will contact you at your registered email address as soon as possible.\n\n"
                f"For reference, here's a summary of your question:\n{question_details}")

    return True, response

# 9. View currently borrowed items:
def view_borrowed_items(user_id):
    conn = connect_to_database()
    cursor = conn.cursor()

    cursor.execute('''
    SELECT
        BT.TransactionID, 
        LI.ItemID, 
        LI.Title, 
        LI.Author, 
        LI.ItemType, 
        BT.BorrowDate, 
        BT.DueDate,
        CASE
            WHEN date('now') > BT.DueDate THEN 'Yes'
            ELSE 'No'
        END AS IsOverdue
    FROM BorrowingTransactions BT JOIN LibraryItems LI ON BT.ItemID = LI.ItemID
    WHERE BT.UserID = ? and BT.ReturnDate IS NULL
    ORDER BY BT.DueDate
    ''', (user_id,))

    results = cursor.fetchall()
    conn.close()

    return results

# Helper function to neatly display borrowed items:
def display_borrowed_items(items):
    if not items:
        print("You have no items currently borrowed.")
        return

    print("\n{:<5} {:<30} {:<20} {:<12} {:<12} {:<10}".format(
        "ID", "Title", "Author", "Due Date", "Transaction", "Overdue"))
    print("-" * 95)

    for item in items:
        due_date = datetime.datetime.strptime(item['DueDate'], "%Y-%m-%d").date()
        print("\n{:<5} {:<30} {:<20} {:<12} {:<12} {:<10}".format(
            item['ItemID'],
            item['Title'][:28] + ".." if len(item['Title']) > 30 else item['Title'],
            item['Author'][:18] + ".." if item['Author'] and len(item['Author']) > 20 else (item['Author'] or "N/A"),
            due_date.strftime("%Y-%m-%d"),
            item['TransactionID'],
            item['IsOverdue']))



# 10. Allow a user to log in to the library system:
def user_login():
    print("\n===== USER LOGIN =====")
    print("1. Login with Library Card Number")
    print("2. Login with Email")
    print("3. Create New Account")
    print("0. Exit")

    choice = input("\nEnter your choice (0-3): ")

    if choice == '0':
        return None

    elif choice == '1':
        card_number = input("Enter your Library Card Number: ")
        user = get_user_by_card(card_number)
        if user:
            print(f"Welcome back, {user['FullName']}!")
            return user['UserID']
        else:
            print("Library card not found.")
            return None

    elif choice == '2':
        email = input("Enter your Email: ")
        user = get_user_by_email(email)
        if user:
            print(f"Welcome back, {user['FullName']}!")
            return user['UserID']
        else:
            print("Email not found.")
            return None

    elif choice == '3':
        return create_new_account()

    else:
        print("Invalid choice. Please try again.")
        return user_login()

# Helper function to get a user by their library card number:
def get_user_by_card(card_number):
    conn = connect_to_database()
    cursor = conn.cursor()

    cursor.execute('''
    SELECT UserID, FullName, AccountStatus
    FROM Users
    WHERE LibraryCardNumber = ?
    ''', (card_number,))

    user = cursor.fetchone()
    conn.close()

    return user

# Helper function to get a user by their email:
def get_user_by_email(email):
    conn = connect_to_database()
    cursor = conn.cursor()

    cursor.execute('''
    SELECT UserID, FullName, AccountStatus
    FROM Users
    WHERE Email = ?
    ''', (email,))

    user = cursor.fetchone()
    conn.close()

    return user

# 11. Create a new user account:
def create_new_account():
    print("\n===== CREATE NEW ACCOUNT =====")

    full_name = input("Enter your full name: ")
    email = input("Enter your email: ")
    phone = input("Enter your phone number: ")
    address = input("Enter your home address: ")

    if get_user_by_email(email):
        print("An account with this email already exists.")
        return None

    print("\nSelect your membership type:")
    print("1. Regular")
    print("2. Student")
    print("3. Senior")
    print("4. Child")

    membership_choice = input("Enter your choice (1-4): ")
    membership_types = {
        '1': 'Regular',
        '2': 'Student',
        '3': 'Senior',
        '4': 'Child'
    }

    if membership_choice not in membership_types:
        print("Invalid choice. Defaulting to Regular membership.")
        membership_type = 'Regular'
    else:
        membership_type = membership_types[membership_choice]

    library_card = generate_library_card()

    conn = connect_to_database()
    cursor = conn.cursor()

    try:
        cursor.execute('''
        INSERT INTO Users (FullName, Email, PhoneNumber, Address, MembershipType, LibraryCardNumber, AccountStatus)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (full_name, email, phone, address, membership_type, library_card, 'Active'))

        user_id = cursor.lastrowid

        conn.commit()
        conn.close()

        print(f"\nAccount created successfully!")
        print(f"Welcome, {full_name}!")
        print(f"Your Library Card Number is: {library_card}")
        print(f"Your User ID is: {user_id}")
        print(f"Please keep these numbers for future reference.")

        return user_id

    except sqlite3.Error as e:
        conn.rollback()
        conn.close()
        print(f"Error creating account: {e}")
        return None

# Helper function to generate a new unique library card number:
def generate_library_card():
    conn = connect_to_database()
    cursor = conn.cursor()

    cursor.execute("SELECT MAX(LibraryCardNumber) FROM Users")
    result = cursor.fetchone()

    highest_card = result[0] if result[0] else 'L10000'

    try:
        numeric_part = int(highest_card[1:])
        new_card = f"L{numeric_part + 1}"
    except ValueError:
        new_card = "L00001"

    conn.close()
    return new_card

        
# 12. Display the main menu of the application:
def main_menu(user_id):
    conn = connect_to_database()
    cursor = conn.cursor()

    cursor.execute("SELECT FullName FROM Users WHERE UserID = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()

    user_name = user['FullName'] if user else "Unknown User"
    
    print("\n===== LIBRARY MANAGEMENT SYSTEM =====")
    print(f"[Logged in as: {user_name}]")
    print(f"User ID: {user_id}")
    print("1. Find an item in the library")
    print("2. Borrow an item from the library")
    print("3. View my borrowed items")
    print("4. Return an item to the library")
    print("5. Donate an item to the library")
    print("6. Find an event in the library")
    print("7. Register for an event in the library")
    print("8. Volunteer for the library")
    print("9. Ask for help from a librarian")
    print("L. Logout")
    print("0. Exit")

    choice = input("\nEnter your choice (0-9, L): ")
    return choice

# Run the library application:
def run_library_app():
    current_user_id = None
    
    while True:
        if current_user_id is None:
            print("\n===== WELCOME TO THE LIBRARY MANAGEMENT SYSTEM =====")
            print("1. Login / Create Account")
            print("0. Exit")
            
            choice = input("\nEnter your choice (0-1): ")

            if choice == '0':
                print("Thank you for using the Library Management System. Goodbye!")
                break
            elif choice == '1':
                current_user_id = user_login()
                if current_user_id is None:
                    continue
            else:
                print("Invalid choice. Please try again.")
                continue
                
        choice = main_menu(current_user_id)

        if choice == '0':
            print("Thank you for using the Library Management System. Goodbye!")
            break

        elif choice == 'L':
            current_user_id = None
            print("You have been logged out.")
            continue
        
        elif choice == '1':
            keyword = input("Enter search term (ID, Title, Author, or Type): ")
            items = find_item(keyword)
            display_item_results(items)
            
        elif choice == '2':
            try:
                item_id = int(input("Enter the Item ID you want to borrow: "))
                success, message = borrow_item(current_user_id, item_id)
                print(message)
            except ValueError:
                print("Invalid input. Please enter a valid Item ID.")

        elif choice == '3':
            items = view_borrowed_items(current_user_id)
            display_borrowed_items(items)

        elif choice == '4':
            try:
                transaction_id = int(input("Enter the Transaction ID for the item you are returning: "))
                success, message = return_item(transaction_id)
                print(message)
            except ValueError:
                print("Invalid input. Please enter a valid numeric Transaction ID.")

        elif choice == '5':
            title = input("Enter the title of the item: ")
            author = input("Enter the name of the author/creator: ")
            item_type = input("Enter the item type (Book, Magazine, CD, etc.): ")
            try:
                year = int(input("Enter the publication year: "))
                isbn = input("Enter the ISBN (if applicable) or press Enter to skip: ") or None
                publisher = input("Enter the publisher (if applicable) or press Enter to skip: ") or None
                success, message = donate_item(title, author, item_type, year, isbn, publisher)
                print(message)
            except ValueError:
                print("Invalid input for year. Please enter a valid numeric year.")

        elif choice == '6':
            keyword = input("Enter the search term (or press Enter to skip): ") or None
            audience_choice = input("Filter by audience (Children, Adults, Seniors) or press Enter for all: ") or None
            if audience_choice and audience_choice not in ['Children', 'Adults', 'Seniors', 'Open to All']:
                print("Invalid audience type. Showing all events instead.")
                audience_choice = None

            future_only = input("Show only future events? (y/n): ").lower() != 'n'
            events = find_events(keyword, audience_choice, future_only)
            display_event_results(events)

        elif choice == '7':
            try:
                event_id = int(input("Enter the Event ID of the event you want to register for: "))
                success, message = register_for_event(current_user_id, event_id)
                print(message)
            except ValueError:
                print("Invalid input. Please enter valid numeric IDs.")

        elif choice == '8':
            full_name = input("Enter your full name: ")
            email = input("Enter your email address: ")
            phone = input("Enter your phone number: ")
            position = input("What position do you want to volunteer for? ")
            availability = input("What is your availability (days/hours)? ")
            success, message = volunteer_for_library(full_name, email, phone, position, availability)
            print(message)

        elif choice == '9':
            try:
                topic = input("What is your question about? ")
                details = input("Please provide more details about your question: ")
                success, message = ask_for_help(current_user_id, topic, details)
                print(message)
            except ValueError:
                print("Invalid input. Please enter a valid numeric User ID.")

        else:
            print("Invalid choice. Please choose a number between 0-9, or L to logout.")

        input("\nPress Enter to continue...")

if __name__ == "__main__":
    run_library_app()