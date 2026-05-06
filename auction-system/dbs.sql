-- Database Creation
DROP DATABASE IF EXISTS AuctionDB;
CREATE DATABASE AuctionDB;
USE AuctionDB;

-- Users Table (3NF)
CREATE TABLE Users (
    UserID INT AUTO_INCREMENT PRIMARY KEY,
    Username VARCHAR(50) UNIQUE NOT NULL,
    Email VARCHAR(100) UNIQUE NOT NULL,
    PasswordHash VARCHAR(255) NOT NULL,
    Contact VARCHAR(15),
    Role ENUM('admin', 'user') DEFAULT 'user',
    RegistrationDate TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_role (Role)
) ENGINE=InnoDB;

-- Items Table (BCNF)
CREATE TABLE Items (
    ItemID INT AUTO_INCREMENT PRIMARY KEY,
    ItemName VARCHAR(100) NOT NULL,
    Description TEXT,
    StartingBid DECIMAL(10,2) NOT NULL,
    SellerID INT NOT NULL,
    CategoryID INT,
    ListedDate TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (SellerID) REFERENCES Users(UserID),
    CHECK (StartingBid > 0),
    INDEX idx_category (CategoryID)
) ENGINE=InnoDB;

-- Auctions Table (3NF)
CREATE TABLE Auctions (
    AuctionID INT AUTO_INCREMENT PRIMARY KEY,
    ItemID INT NOT NULL,
    StartTime DATETIME NOT NULL,
    EndTime DATETIME NOT NULL,
    Status ENUM('Open', 'Closed') DEFAULT 'Open',
    CreatedBy INT NOT NULL,  -- Admin ID
    WinnerID INT,
    FOREIGN KEY (ItemID) REFERENCES Items(ItemID),
    FOREIGN KEY (CreatedBy) REFERENCES Users(UserID),
    FOREIGN KEY (WinnerID) REFERENCES Users(UserID),
    INDEX idx_status (Status),
    INDEX idx_endtime (EndTime)
) ENGINE=InnoDB;

-- Bids Table (BCNF)
CREATE TABLE Bids (
    BidID INT AUTO_INCREMENT PRIMARY KEY,
    AuctionID INT NOT NULL,
    UserID INT NOT NULL,
    Amount DECIMAL(10,2) NOT NULL,
    BidTime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (AuctionID) REFERENCES Auctions(AuctionID),
    FOREIGN KEY (UserID) REFERENCES Users(UserID),
    INDEX idx_auction (AuctionID),
    INDEX idx_amount (Amount DESC)
) ENGINE=InnoDB;

-- Payments Table (3NF)
CREATE TABLE Payments (
    PaymentID INT AUTO_INCREMENT PRIMARY KEY,
    AuctionID INT NOT NULL,
    UserID INT NOT NULL,
    Amount DECIMAL(10,2) NOT NULL,
    PaymentMethod ENUM('COD', 'UPI', 'Card') NOT NULL,
    PaymentStatus ENUM('Pending', 'Completed') DEFAULT 'Pending',
    TransactionTime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (AuctionID) REFERENCES Auctions(AuctionID),
    FOREIGN KEY (UserID) REFERENCES Users(UserID)
) ENGINE=InnoDB;

-- Shipping Table (2NF)
CREATE TABLE Shipping (
    ShippingID INT AUTO_INCREMENT PRIMARY KEY,
    PaymentID INT NOT NULL,
    Address TEXT NOT NULL,
    Method ENUM('Express', 'Standard') NOT NULL,
    Cost DECIMAL(10,2) NOT NULL,
    Status ENUM('Processing', 'Shipped', 'Delivered') DEFAULT 'Processing',
    FOREIGN KEY (PaymentID) REFERENCES Payments(PaymentID)
) ENGINE=InnoDB;

-- Sample Admin Insert
INSERT INTO Users (Username, Email, PasswordHash, Role) 
VALUES ('admin', 'admin@auction.com', SHA2('adminpass', 256), 'admin');

-- PL/SQL Procedures
DELIMITER $$

-- Create Auction Procedure (Admin)
CREATE PROCEDURE CreateAuction(
    IN p_ItemID INT,
    IN p_StartTime DATETIME,
    IN p_EndTime DATETIME,
    IN p_AdminID INT
)
BEGIN
    INSERT INTO Auctions (ItemID, StartTime, EndTime, CreatedBy)
    VALUES (p_ItemID, p_StartTime, p_EndTime, p_AdminID);
END$$

-- Place Bid Procedure (User) - Modified
CREATE PROCEDURE PlaceBid(
    IN p_AuctionID INT,
    IN p_UserID INT,
    IN p_Amount DECIMAL(10,2)
)
BEGIN
    DECLARE current_max DECIMAL(10,2) DEFAULT NULL;
    DECLARE starting_bid DECIMAL(10,2) DEFAULT NULL;
    DECLARE min_required DECIMAL(10,2) DEFAULT NULL;

    -- Get the current maximum bid
    SELECT MAX(Amount) INTO current_max FROM Bids WHERE AuctionID = p_AuctionID;

    -- Get the starting bid
    SELECT i.StartingBid INTO starting_bid 
    FROM Items i
    JOIN Auctions a ON i.ItemID = a.ItemID
    WHERE a.AuctionID = p_AuctionID;

    -- Determine the minimum required bid
    IF current_max IS NULL THEN
        SET min_required = starting_bid + 1;
    ELSE
        SET min_required = current_max + 1;
    END IF;

    -- Check if the bid is valid
    IF p_Amount >= min_required THEN
        INSERT INTO Bids (AuctionID, UserID, Amount)
        VALUES (p_AuctionID, p_UserID, p_Amount);
    ELSE
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = CONCAT('Bid amount must be at least ', min_required);
    END IF;
END$$

-- Trigger: Auto-close Auctions
CREATE TRIGGER UpdateAuctionStatus
BEFORE INSERT ON Bids
FOR EACH ROW
BEGIN
    DECLARE auction_end DATETIME;
    
    SELECT EndTime INTO auction_end FROM Auctions 
    WHERE AuctionID = NEW.AuctionID;
    
    IF NOW() > auction_end THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Auction has already closed';
    END IF;
END$$

-- Function: Get Highest Bid
CREATE FUNCTION GetHighestBid(p_AuctionID INT) 
RETURNS DECIMAL(10,2)
READS SQL DATA
BEGIN
    DECLARE max_bid DECIMAL(10,2);
    SELECT MAX(Amount) INTO max_bid FROM Bids
    WHERE AuctionID = p_AuctionID;
    RETURN max_bid;
END$$

-- Event for Auto-Closing and Winner Assignment
CREATE EVENT update_auction_winners
ON SCHEDULE EVERY 1 MINUTE
DO
BEGIN
    -- Close expired auctions
    UPDATE Auctions 
    SET Status = 'Closed' 
    WHERE EndTime <= NOW() 
      AND Status = 'Open';

    -- Set winners for closed auctions
    UPDATE Auctions a
    JOIN (
        SELECT b.AuctionID, b.UserID
        FROM Bids b
        INNER JOIN (
            SELECT AuctionID, MAX(Amount) AS MaxBid
            FROM Bids
            GROUP BY AuctionID
        ) max_bids ON b.AuctionID = max_bids.AuctionID AND b.Amount = max_bids.MaxBid
    ) winners ON a.AuctionID = winners.AuctionID
    SET a.WinnerID = winners.UserID
    WHERE a.Status = 'Closed' 
      AND a.WinnerID IS NULL;
END$$

DELIMITER ;

-- Views (Practical 8)
CREATE VIEW ActiveAuctions AS
SELECT a.AuctionID, i.ItemName, MAX(b.Amount) AS CurrentBid
FROM Auctions a
JOIN Items i ON a.ItemID = i.ItemID
LEFT JOIN Bids b ON a.AuctionID = b.AuctionID
WHERE a.Status = 'Open'
GROUP BY a.AuctionID;

-- Query Optimization Explain Plan
EXPLAIN SELECT * FROM ActiveAuctions WHERE CurrentBid > 1000;

-- Sample Data
INSERT INTO Users (Username, Email, PasswordHash, Contact) VALUES
('john', 'john@example.com', SHA2('john123', 256), '1234567890'),
('emma', 'emma@example.com', SHA2('emma123', 256), '0987654321');

INSERT INTO Items (ItemName, Description, StartingBid, SellerID) VALUES
('Vintage Camera', 'Film camera from 1970s', 5000, 2),
('Smart Watch', 'Brand new fitness tracker', 2000, 3),
('Study Table', 'Broad wooden study table', 7000, 3);
