USE ROLE ACCOUNTADMIN;                          -- top admin role; only it can create resource monitors

CREATE RESOURCE MONITOR IF NOT EXISTS datum_monthly  -- a spending guard named for its job
  WITH CREDIT_QUOTA = 10                        -- budget: 10 credits per period
  FREQUENCY = MONTHLY                           -- the budget resets each month
  START_TIMESTAMP = IMMEDIATELY                 -- start counting now
  TRIGGERS ON 80 PERCENT DO NOTIFY              -- at 8 credits: send a warning
           ON 100 PERCENT DO SUSPEND;           -- at 10 credits: stop the warehouse once running queries finish

USE ROLE SYSADMIN;                              -- switch to the everyday role that should own objects

CREATE WAREHOUSE IF NOT EXISTS datum_wh         -- compute that runs queries (storage is billed separately)
  WAREHOUSE_SIZE = XSMALL                       -- smallest size: 1 credit per hour while running
  AUTO_SUSPEND = 60                             -- turn off after 60 idle seconds
  AUTO_RESUME = TRUE                            -- turn back on when a query arrives
  INITIALLY_SUSPENDED = TRUE;                   -- don't start, or bill, at creation

USE ROLE ACCOUNTADMIN;                          -- back to the top role: only it can attach a monitor
ALTER WAREHOUSE datum_wh SET RESOURCE_MONITOR = datum_monthly;  -- connect the guard to the warehouse


-- Syntax: IF NOT EXISTS makes the statement safe to rerun, because it skips objects that already exist. TRIGGERS ... DO sets what happens at each spending threshold.

-- Concept: Snowflake separates storage from compute. You pay for compute only while a warehouse is running, which is why auto-suspend is the biggest cost lever. Roles control who can do what. ACCOUNTADMIN handles billing-level settings; SYSADMIN owns databases and warehouses.

-- Design decision: objects are owned by SYSADMIN, and ACCOUNTADMIN is used only for the two billing steps. That’s least privilege: you don’t run daily work with the master key. 10 credits is roughly $20–30 a month (🟡 depends on your Snowflake edition). The NOTIFY warning only reaches you if email notifications are turned on in your Snowsight profile.