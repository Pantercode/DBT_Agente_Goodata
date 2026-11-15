{% test soma_igual_a(model, coluna, valor) %}
    select sum({{ coluna }}) as soma
    from {{ model }}
    having sum({{ coluna }}) <> {{ valor }}
{% endtest %}
