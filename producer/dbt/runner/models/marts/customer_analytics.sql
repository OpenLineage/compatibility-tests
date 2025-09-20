{{ config(materialized='table') }}

select
    c.customer_id,
    c.customer_name,
    c.email,
    c.segment,
    c.value_tier,
    count(o.order_id) as total_orders,
    sum(o.completed_amount) as total_revenue,
    avg(o.completed_amount) as avg_order_value,
    max(o.order_date) as last_order_date
from {{ ref('stg_customers') }} c
left join {{ ref('stg_orders') }} o 
    on c.customer_id = o.customer_id
group by 
    c.customer_id,
    c.customer_name,
    c.email,
    c.segment,
    c.value_tier