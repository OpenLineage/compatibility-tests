{{ config(materialized='table') }}

select
    customer_id,
    name as customer_name,
    email,
    registration_date,
    segment,
    case 
        when segment = 'enterprise' then 'high_value'
        when segment = 'premium' then 'medium_value'
        else 'standard_value'
    end as value_tier
from {{ ref('raw_customers') }}