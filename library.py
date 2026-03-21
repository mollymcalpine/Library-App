import sqlite3
import datetime
from datetime import timedelta, date
import random

conn = sqlite3.connect('library.db')
cursor = conn.cursor()

# Create tables:
# 1. Library Items:
cursor.execute('''
CREATE TABLE IF NOT EXISTS LibraryItems (
    ItemID INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    Title NVARCHAR(200) NOT NULL,
    Author NVARCHAR(200),
    ItemType NVARCHAR(200) NOT NULL,
    PublicationYear INTEGER,
    ISBN NVARCHAR(13) UNIQUE,
    Publisher NVARCHAR(100),
    AvailabilityStatus NVARCHAR(100) NOT NULL DEFAULT 'Available',
    Location NVARCHAR(200),
    DigitalAccessLink NVARCHAR(200),
    CHECK (AvailabilityStatus IN ('Available', 'Borrowed', 'Reserved'))
);
''')

# 2. Users:
cursor.execute('''
CREATE TABLE IF NOT EXISTS Users (
    UserID INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    FullName NVARCHAR(200) NOT NULL,
    Email NVARCHAR(200) NOT NULL UNIQUE,
    PhoneNumber NVARCHAR(12),
    Address NVARCHAR(100),
    MembershipType NVARCHAR(100) NOT NULL,
    LibraryCardNumber NVARCHAR(100) NOT NULL UNIQUE,
    AccountStatus NVARCHAR(9) NOT NULL DEFAULT 'Active',
    CHECK (AccountStatus IN ('Active', 'Suspended'))
);
''')

# 3. Borrowing Transactions
cursor.execute('''
CREATE TABLE IF NOT EXISTS BorrowingTransactions (
    TransactionID INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    UserID INTEGER NOT NULL,
    ItemID INTEGER NOT NULL,
    BorrowDate DATE NOT NULL,
    DueDate DATE NOT NULL,
    ReturnDate DATE,
    OverdueStatus NVARCHAR(3) DEFAULT 'No',
    FineAmount NUMERIC(5, 2) DEFAULT 0.00,
    FOREIGN KEY (UserID) REFERENCES Users(UserID),
    FOREIGN KEY (ItemID) REFERENCES LibraryItems(ItemID),
    CHECK (OverdueStatus IN ('Yes', 'No'))
);
''')

# 4. Fines
cursor.execute('''
CREATE TABLE IF NOT EXISTS Fines (
    FineID INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    UserID INTEGER NOT NULL,
    TransactionID INTEGER NOT NULL,
    AmountDue NUMERIC(5, 2) NOT NULL,
    PaidStatus NVARCHAR(100) NOT NULL DEFAULT 'No',
    PaymentDate DATE,
    FOREIGN KEY (UserID) REFERENCES Users(UserID),
    FOREIGN KEY (TransactionID) REFERENCES BorrowingTransactions(TransactionID),
    CHECK (PaidStatus IN ('Yes', 'No'))
);
''')

# 5. Events
cursor.execute('''
CREATE TABLE IF NOT EXISTS Events (
    EventID INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    EventName NVARCHAR(200) NOT NULL,
    EventDate DATETIME NOT NULL,
    EventDescription NVARCHAR(300),
    TargetAudience NVARCHAR(12) NOT NULL DEFAULT 'Open to All',
    Location NVARCHAR(100) NOT NULL,
    CHECK (TargetAudience IN ('Children', 'Adults', 'Seniors', 'Open to All'))
);
''')

# 6. Event Attendance:
cursor.execute('''
CREATE TABLE IF NOT EXISTS EventAttendance (
    AttendanceID INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    EventID INTEGER NOT NULL,
    UserID INTEGER NOT NULL,
    FOREIGN KEY (EventID) REFERENCES Events(EventID),
    FOREIGN KEY (UserID) REFERENCES Users(UserID),
    UNIQUE (EventID, UserID)
);
''')

# 7. Personnel:
cursor.execute('''
CREATE TABLE IF NOT EXISTS Personnel (
    StaffID INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    FullName NVARCHAR(200) NOT NULL,
    Position NVARCHAR(200) NOT NULL,
    Email NVARCHAR(200) NOT NULL UNIQUE,
    PhoneNumber NVARCHAR(12),
    WorkSchedule NVARCHAR(300)
);
''')

# 8. Future Acquisitions:
cursor.execute('''
CREATE TABLE IF NOT EXISTS FutureAcquisitions (
    AcquisitionID INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    Title NVARCHAR(200) NOT NULL,
    Author NVARCHAR(200),
    RequestedBy INTEGER NOT NULL,
    ApprovalStatus NVARCHAR NOT NULL DEFAULT 'Pending',
    RequestDate DATE NOT NULL,
    CHECK (ApprovalStatus IN ('Pending', 'Approved', 'Denied'))
);
''')

# Create triggers:

# Trigger to update item availability to 'Borrowed' when a new transaction is inserted:
cursor.execute('''
CREATE TRIGGER IF NOT EXISTS update_item_borrowed
AFTER INSERT ON BorrowingTransactions
FOR EACH ROW
BEGIN 
    UPDATE LibraryItems SET AvailabilityStatus = 'Borrowed'
    WHERE ItemID = NEW.ItemID;
END;
''')

# Trigger to update item availability to 'Available' when an item is returned:
cursor.execute('''
CREATE TRIGGER IF NOT EXISTS update_item_returned
AFTER UPDATE ON BorrowingTransactions
FOR EACH ROW
WHEN New.ReturnDate IS NOT NULL AND OLD.ReturnDate IS NULL
BEGIN
    UPDATE LibraryItems SET AvailabilityStatus = 'Available'
    WHERE ItemID = NEW.ItemID;
END;
''')

# Trigger to calculate overdue status, and fine when an item is returned late:
cursor.execute('''
CREATE TRIGGER IF NOT EXISTS calculate_fine
AFTER UPDATE ON BorrowingTransactions
FOR EACH ROW
WHEN NEW.ReturnDate IS NOT NULL AND OLD.ReturnDATE IS NULL
BEGIN
    UPDATE BorrowingTransactions
    SET OverdueStatus = CASE
                            WHEN NEW.ReturnDate > NEW.DueDate THEN 'Yes'
                            ELSE 'No'
                        END,
        FineAmount = CASE
                        WHEN NEW.ReturnDate > NEW.DueDate
                        THEN NEW.ReturnDate - NEW.DueDate * 0.5
                        ELSE 0
                     END
    WHERE TransactionID = NEW.TransactionID;

    INSERT INTO Fines (UserID, TransactionID, AmountDue)
    SELECT UserID, TransactionID, FineAmount
    FROM BorrowingTransactions
    WHERE TransactionID = NEW.TransactionID AND FineAmount > 0;
END;
''')

# Create indexes:
cursor.execute('CREATE INDEX IF NOT EXISTS idx_items_title ON LibraryItems(Title);')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_items_author ON LibraryItems(Author);')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_items_isbn ON LibraryItems(ISBN);')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_name ON Users(FullName);')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_card ON Users(LibraryCardNumber);')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_transactions_user ON BorrowingTransactions(UserID);')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_transactions_item ON BorrowingTransactions(ItemID);')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_events_date ON Events(EventDate);')

# Create a view to easily see all overdue items:
cursor.execute('''
CREATE VIEW IF NOT EXISTS OverdueItems AS
SELECT
    BT.TransactionID,
    U.FullName AS UserName,
    U.Email AS UserEmail,
    U.PhoneNumber AS UserPhone,
    LI.Title AS ItemTitle,
    LI.ItemType,
    BT.BorrowDate,
    BT.DueDate,
    julianday('now') - julianday(BT.DueDate) AS DaysOverdue,
    BT.FineAmount
FROM 
    BorrowingTransactions BT 
JOIN 
    Users U ON BT.UserID = U.UserID
JOIN
    LibraryItems LI ON BT.ItemID = LI.ItemID
WHERE 
    BT.ReturnDate IS NULL AND julianday('now') > julianday(BT.DueDate);
''')

print("Library database created successfully.")

# Helper function to generate random dates:
def random_date(start_date, end_date):
    time_between_dates = end_date - start_date
    days_between_dates = time_between_dates.days
    random_number_of_days = random.randrange(days_between_dates)
    return start_date + timedelta(days=random_number_of_days)

# Helper function to format date for SQLite:
def format_date(date_obj):
    return date_obj.strftime("%Y-%m-%d")

print("Populating the database with sample data...")

# Populate the tables:

# 1. Populate LibraryItems table:
print("Populating LibraryItems table...")
library_items = [
    ("To Kill a Mockingbird", "Harper Lee", "Book", 1960, "9780446310789", "J. B. Lippincott & Co.", "Available", "Fiction Section A3", None),
    ("1984", "George Orwell", "Book", 1949, "9780451524935", "Secker & Warburg", "Available", "Fiction Section B2", None),
    ("The Great Gatsby", "F. Scott Fitzgerald", "Book", 1925, "9780743273565", "Charles Scribner's Sons", "Available", "Fiction Section A1", None),
    ("Pride and Prejudice", "Jane Austen", "Book", 1813, "9780141439518", "T. Egerton", "Available", "Fiction Section C4", None),
    ("The Catcher in the Rye", "J.D. Salinger", "Book", 1951, "9780316769488", "Little, Brown and Company", "Available", "Fiction Section B5", None),
    ("National Geographic", "Various", "Magazine", 2023, "00279358", "National Geographic Partners", "Available", "Periodicals Section P1", None),
    ("Scientific American", "Various", "Journal", 2023, "00368733", "Springer Nature", "Available", "Periodicals Section P2", None),
    ("The Beatles: Abbey Road", "The Beatles", "CD", 1969, "B0025KVLUQ", "Apple Records", "Available", "Music Section M1", None),
    ("The Theory of Everything", "Various", "DVD", 2014, "B00QR4GQYY", "Universal Pictures", "Available", "Media Section D3", None),
    ("Python Programming", "John Smith", "Book", 2022, "9781449355739", "O'Reilly Media", "Available", "Non-Fiction Section N2", None),
    ("Introduction to Algorithms", "Thomas H. Cormen", "Book", 2009, "9780262033848", "MIT Press", "Available", "Non-Fiction Section N3", None),
    ("The New Yorker", "Various", "Magazine", 2023, "0028792X", "Condé Nast", "Available", "Periodicals Section P3", None),
    ("Pink Floyd: The Dark Side of the Moon", "Pink Floyd", "Vinyl Record", 1973, "B0006675XS", "Harvest", "Available", "Music Section M2", None),
    ("JavaScript: The Good Parts", "Douglas Crockford", "Book", 2008, "9780596517748", "O'Reilly Media", "Available", "Non-Fiction Section N4", "https://library.example.com/ebooks/js-good-parts"),
    ("Harvard Business Review", "Various", "Journal", 2023, "00178012", "Harvard Business Publishing", "Available", "Periodicals Section P4", "https://library.example.com/journals/hbr")
]

# Insert items into Library Items table:
for item in library_items:
    cursor.execute('''
    INSERT INTO LibraryItems (Title, Author, ItemType, PublicationYear, ISBN, Publisher, AvailabilityStatus, Location, DigitalAccessLink)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', item)

# 2. Populate Users table:
print("Populating Users table...")

users = [
    ("John Doe", "john.doe@email.com", "604-123-4567", "123 Main St, Anytown", "Child", "L10001", "Active"),
    ("Jane Smith", "jane.smith@email.com", "555-234-5678", "456 Oak Ave, Anytown", "Student", "L10002", "Active"),
    ("Robert Johnson", "robert.j@email.com", "555-345-6789", "789 Pine St, Anytown", "Senior", "L10003", "Active"),
    ("Emily Davis", "emily.d@email.com", "555-456-7890", "101 Maple Dr, Anytown", "Regular", "L10004", "Active"),
    ("Michael Wilson", "michael.w@email.com", "555-567-8901", "202 Elm St, Anytown", "Student", "L10005", "Active"),
    ("Sarah Brown", "sarah.b@email.com", "555-678-9012", "303 Cedar Ave, Anytown", "Child", "L10006", "Active"),
    ("David Miller", "david.m@email.com", "555-789-0123", "404 Birch Ln, Anytown", "Senior", "L10007", "Active"),
    ("Jennifer Taylor", "jennifer.t@email.com", "555-890-1234", "505 Walnut St, Anytown", "Student", "L10008", "Active"),
    ("Christopher Anderson", "chris.a@email.com", "555-901-2345", "606 Spruce Dr, Anytown", "Regular", "L10009", "Suspended"),
    ("Jessica Thomas", "jessica.t@email.com", "555-012-3456", "707 Willow Ave, Anytown", "Child", "L10010", "Active"),
    ("Matthew Jackson", "matt.j@email.com", "555-123-7890", "808 Ash St, Anytown", "Student", "L10011", "Active"),
    ("Amanda White", "amanda.w@email.com", "555-234-8901", "909 Cherry Ln, Anytown", "Senior", "L10012", "Active"),
    ("Daniel Harris", "daniel.h@email.com", "555-345-9012", "1010 Oak Dr, Anytown", "Regular", "L10013", "Active"),
    ("Michelle Martin", "michelle.m@email.com", "555-456-0123", "1111 Pine Ave, Anytown", "Student", "L10014", "Active"),
    ("Kevin Thompson", "kevin.t@email.com", "555-567-1234", "1212 Maple St, Anytown", "Regular", "L10015", "Active")
]

# Insert users into Users table:
for user in users:
    cursor.execute('''
    INSERT INTO Users (FullName, Email, PhoneNumber, Address, MembershipType, LibraryCardNumber, AccountStatus)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', user)


# 3. Populate BorrowingTransactions table:
print("Populating BorrowingTransactions table...")

cursor.execute("SELECT UserID FROM Users")
user_ids = [row[0] for row in cursor.fetchall()]

cursor.execute("SELECT ItemID FROM LibraryItems")
item_ids = [row[0] for row in cursor.fetchall()]

# Generate random transactions:
today = date.today()
transactions = []

for i in range(15):
    user_id = random.choice(user_ids)
    item_id = random.choice(item_ids)
    borrow_date = random_date(today - timedelta(days=60), today - timedelta(days=1))
    due_date = borrow_date + timedelta(days=14)

    if random.random() < 0.7:
        return_date = random_date(borrow_date, today)
        overdue_status = "Yes" if return_date > due_date else "No"
        fine_amount = (return_date - due_date).days * 0.5 if return_date > due_date else 0
        fine_amount = max(0, fine_amount)
    else:
        return_date = None
        overdue_status = "Yes" if today > due_date else "No"
        fine_amount = (today - due_date).days * 0.5 if today > due_date else 0
        fine_amount = max(0, fine_amount)

    transactions.append((user_id, item_id, format_date(borrow_date), format_date(due_date), format_date(return_date) if return_date else None, overdue_status, fine_amount))

# Insert transactions into BorrowingTransactions table:
for transaction in transactions:
    cursor.execute('''
    INSERT INTO BorrowingTransactions (UserId, ItemID, BorrowDate, DueDate, ReturnDate, OverdueStatus, FineAmount)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', transaction)


# 4. Populate Fines table:
print("Populating Fines table...")

cursor.execute("SELECT TransactionID, UserID, FineAmount FROM BorrowingTransactions WHERE FineAmount > 0")
fine_transactions = cursor.fetchall()

fines = []
for trans_id, user_id, amount in fine_transactions:
    paid_status = "Yes" if random.random() < 0.5 else "No"
    payment_date = format_date(random_date(today - timedelta(days=30), today)) if paid_status == "Yes" else None
    fines.append((user_id, trans_id, amount, paid_status, payment_date))

# Insert random fines to ensure at least 10 records:
while len(fines) < 10:
    trans_id = random.choice([row[0] for row in fine_transactions])
    user_id = random.choice(user_ids)
    amount = round(random.uniform(0.5, 20.0), 2)
    paid_status = "Yes" if random.random() < 0.5 else "No"
    payment_date = format_date(random_date(today - timedelta(days=30), today)) if paid_status == "Yes" else None
    fines.append((user_id, trans_id, amount, paid_status, payment_date))

# Insert fines into Fines table:
for fine in fines:
    cursor.execute('''
    INSERT INTO Fines (UserID, TransactionID, AmountDue, PaidStatus, PaymentDate)
    VALUES (?, ?, ?, ?, ?)
    ''', fine)

# 5. Populate Events table:
print("Populating Events table...")

events = [
    ("Book Club: To Kill a Mockingbird", format_date(today + timedelta(days=7)), "Discussion about Harper Lee's classic novel", "Adults", "Meeting Room A"),
    ("Story Time for Kids", format_date(today + timedelta(days=3)), "Reading of children's books with activities", "Children", "Children's Area"),
    ("Author Talk: Local Writers", format_date(today + timedelta(days=14)), "Local authors discuss their works and writing process", "Open to All", "Auditorium"),
    ("Poetry Reading Night", format_date(today + timedelta(days=21)), "Open mic for poetry enthusiasts", "Open to All", "Café Area"),
    ("Film Screening: Classic Cinema", format_date(today + timedelta(days=10)), "Screening of a classic film with discussion", "Adults", "Media Room"),
    ("Computer Basics Workshop", format_date(today + timedelta(days=5)), "Learn computer fundamentals for beginners", "Seniors", "Computer Lab"),
    ("Art Exhibition Opening", format_date(today + timedelta(days=9)), "Opening reception for new art exhibition", "Open to All", "Gallery Space"),
    ("Science Fair for Students", format_date(today + timedelta(days=28)), "Students present science projects", "Children", "Main Hall"),
    ("Book Sale Fundraiser", format_date(today + timedelta(days=15)), "Annual book sale to support library programs", "Open to All", "Community Room"),
    ("Career Development Workshop", format_date(today + timedelta(days=17)), "Resume building and job search strategies", "Adults", "Meeting Room B"),
    ("Chess Club Meeting", format_date(today + timedelta(days=4)), "Weekly meeting of the library chess club", "Open to All", "Game Room"),
    ("Language Exchange", format_date(today + timedelta(days=11)), "Practice speaking different languages with others", "Open to All", "Study Room 2"),
    ("Gardening Workshop", format_date(today + timedelta(days=19)), "Tips and techniques for home gardening", "Open to All", "Outdoor Patio"),
    ("History Lecture Series", format_date(today + timedelta(days=25)), "Local historian discusses regional history", "Adults", "Lecture Hall"),
    ("Teen Book Club", format_date(today + timedelta(days=8)), "Discussion group for teenage readers", "Children", "Teen Zone")
]

# Insert events into Events table:
for event in events:
    cursor.execute('''
    INSERT INTO Events (EventName, EventDate, EventDescription, TargetAudience, Location)
    VALUES (?, ?, ?, ?, ?)
    ''', event)

# 6. Populate EventAttendance table:
print("Populating EventAttendance table...")

cursor.execute("SELECT EventID FROM Events")
event_ids = [row[0] for row in cursor.fetchall()]

attendances = []
for i in range(20):
    event_id = random.choice(event_ids)
    user_id = random.choice(user_ids)
    while (event_id, user_id) in [(a[0], a[1]) for a in attendances]:
        event_id = random.choice(event_ids)
        user_id = random.choice(user_ids)

    registered_date = format_date(random_date(today - timedelta(days=30), today))
    attendances.append((event_id, user_id))

# Insert attendances into EventAttendance table:
for attendance in attendances:
    cursor.execute('''
    INSERT INTO EventAttendance (EventID, UserID)
    VALUES (?, ?)
    ''', attendance)

# 7. Populate Personnel table:
print("Populating Personnel table...")

personnel = [
    ("Margaret Johnson", "Head Librarian", "margaret.j@library.org", "555-111-2222", "Mon-Fri, 9am-5pm"),
    ("Robert Chen", "Reference Librarian", "robert.c@library.org", "555-222-3333", "Tue-Sat, 10am-6pm"),
    ("Sophia Rodriguez", "Children's Librarian", "sophia.r@library.org", "555-333-4444", "Mon-Fri, 8am-4pm"),
    ("James Wilson", "IT Specialist", "james.w@library.org", "555-444-5555", "Mon, Wed, Fri, 9am-5pm"),
    ("Emma Davis", "Administrative Assistant", "emma.d@library.org", "555-555-6666", "Mon-Fri, 8:30am-4:30pm"),
    ("Noah Thompson", "Security Officer", "noah.t@library.org", "555-666-7777", "Mon-Thu, 12pm-8pm"),
    ("Olivia Martinez", "Events Coordinator", "olivia.m@library.org", "555-777-8888", "Wed-Sun, 11am-7pm"),
    ("William Taylor", "Library Assistant", "william.t@library.org", "555-888-9999", "Sat-Wed, 1pm-9pm"),
    ("Ava Anderson", "Cataloging Specialist", "ava.a@library.org", "555-999-0000", "Mon-Fri, 7am-3pm"),
    ("Ethan Thomas", "Security Officer", "ethan.t@library.org", "555-000-1111", "Thu-Mon, 4pm-12am"),
    ("Isabella Jackson", "Library Assistant", "isabella.j@library.org", "555-123-7654", "Mon-Fri, 9am-5pm"),
    ("Michael Brown", "Archivist", "michael.b@library.org", "555-234-8765", "Tue-Sat, 10am-6pm")
]

# Insert personnel into Personnel table:
for person in personnel:
    cursor.execute('''
    INSERT INTO Personnel (FullName, Position, Email, PhoneNumber, WorkSchedule)
    VALUES (?, ?, ?, ?, ?)
    ''', person)

# 8. Populate FutureAcquisitions table:
print("Populating FutureAcquisitions table...")

requesters = user_ids + [p+1 for p in range(len(personnel))]

acquisitions = [
    ("The Midnight Library", "Matt Haig", random.choice(requesters), "Pending", format_date(random_date(today - timedelta(days=30), today))),
    ("Project Hail Mary", "Andy Weir", random.choice(requesters), "Approved", format_date(random_date(today - timedelta(days=45), today))),
    ("Klara and the Sun", "Kazuo Ishiguro", random.choice(requesters), "Pending", format_date(random_date(today - timedelta(days=20), today))),
    ("The Four Winds", "Kristin Hannah", random.choice(requesters), "Denied", format_date(random_date(today - timedelta(days=60), today))),
    ("A Promised Land", "Barack Obama", random.choice(requesters), "Approved", format_date(random_date(today - timedelta(days=90), today))),
    ("The Invisible Life of Addie LaRue", "V.E. Schwab", random.choice(requesters), "Pending", format_date(random_date(today - timedelta(days=15), today))),
    ("Hamnet", "Maggie O'Farrell", random.choice(requesters), "Approved", format_date(random_date(today - timedelta(days=75), today))),
    ("The Vanishing Half", "Brit Bennett", random.choice(requesters), "Pending", format_date(random_date(today - timedelta(days=25), today))),
    ("Educated", "Tara Westover", random.choice(requesters), "Approved", format_date(random_date(today - timedelta(days=55), today))),
    ("Where the Crawdads Sing", "Delia Owens", random.choice(requesters), "Denied", format_date(random_date(today - timedelta(days=40), today))),
    ("The Guest List", "Lucy Foley", random.choice(requesters), "Pending", format_date(random_date(today - timedelta(days=10), today))),
    ("The Silent Patient", "Alex Michaelides", random.choice(requesters), "Approved", format_date(random_date(today - timedelta(days=80), today)))
]

# Insert acquisitions into FutureAcquisitions table:
for acquisition in acquisitions:
    cursor.execute('''
    INSERT INTO FutureAcquisitions (Title, Author, RequestedBy, ApprovalStatus, RequestDate)
    VALUES (?, ?, ?, ?, ?)
    ''', acquisition)

# Commit the changes and close the connection:
if conn:
    conn.commit()
    conn.close()

print("All tables have been successfully populated with sample data.")

# Verify correct data insertion:
def verify_data():
    conn = sqlite3.connect('library.db')
    cursor = conn.cursor()

    tables = ["LibraryItems", "Users", "BorrowingTransactions", "Fines", "Events", "EventAttendance", "Personnel", "FutureAcquisitions"]

    print("\nData Verification:")
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"- {table}: {count} records")

    conn.close()

verify_data()

    