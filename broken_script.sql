CREATE TABLE raw_users (id INT, name VARCHAR);
INSERT INTO raw_users VALUES (1, 'Alice'), (2, 'Bob'), (3, NULL);

CREATE TABLE orders (id INT, user_id INT, amount INT, order_date DATE);
-- Create a Cartesian Explosion by duplicating an order row
INSERT INTO orders VALUES (101, 1, 150, '2026-01-01'), (101, 1, 150, '2026-01-01'), (102, 1, 50, '2026-01-02'), (103, 2, 200, '2026-01-03');

WITH first_cte AS (
    SELECT id, name FROM raw_users
),
second_cte AS (
    SELECT id, name, 'active' as status 
    FROM first_cte
    WHERE name IS NOT NULL
),
third_cte AS (
    SELECT s.id, s.name, o.order_date
    FROM second_cte s
    JOIN orders o ON s.id = o.user_id
    WHERE o.amount > 100
),
fourth_cte AS (
    SELECT * FROM third_cte WHERE name = 'Charlie'
)
SELECT * FROM fourth_cte;
