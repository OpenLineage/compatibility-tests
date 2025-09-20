{{ config(materialized='table') }}

select
    order_id,
    customer_id,
    order_date,
    amount,
    status,
    case 
        when status = 'completed' then amount
        else 0
    end as completed_amount
from {{ ref('raw_orders') }}
where status != 'cancelled'