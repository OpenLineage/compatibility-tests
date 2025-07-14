DROP TABLE IF EXISTS transactions;
CREATE EXTERNAL TABLE transactions (SubmissionDate DATE, TransactionAmount DOUBLE, TransactionType STRING) STORED AS PARQUET ;



DROP TABLE IF EXISTS monthly_transaction_summary;
  CREATE TABLE monthly_transaction_summary
  STORED AS PARQUET
  AS
  SELECT
      TRUNC(submissiondate, 'MM') AS Month,
      transactiontype,
      SUM(transactionamount) AS TotalAmount,
      COUNT(\*) AS TransactionCount
  FROM
      transactions
  GROUP BY
      TRUNC(submissiondate, 'MM'),
      transactiontype
  ORDER BY
      Month,
      transactiontype;"