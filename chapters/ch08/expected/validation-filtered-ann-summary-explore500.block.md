| rung | documents | share | strategy | agreement@100 | empty queries | p50 | p95 | algorithm |
|---|---|---|---|---|---|---|---|---|
| has_brand | 95,944 | 94.67% | default | 0.990 | 0 / 735 | 14.7 ms | 17.3 ms | index top k using filter |
| has_brand | 95,944 | 94.67% | post | 0.937 | 0 / 735 | 15.0 ms | 17.6 ms | index top k |
| has_brand | 95,944 | 94.67% | pre | 0.990 | 0 / 735 | 15.1 ms | 17.7 ms | index top k using filter |
| has_description | 51,995 | 51.31% | default | 0.993 | 0 / 735 | 16.1 ms | 19.0 ms | index top k using filter |
| has_description | 51,995 | 51.31% | exact | 1.000 | 0 / 735 | 17.4 ms | 20.0 ms | exact |
| has_description | 51,995 | 51.31% | post | 0.898 | 0 / 735 | 15.4 ms | 18.3 ms | index top k |
| has_description | 51,995 | 51.31% | pre | 0.993 | 0 / 735 | 16.5 ms | 19.3 ms | index top k using filter |
| marketplace | 5,397 | 5.33% | default | 0.822 | 99 / 735 | 15.7 ms | 18.5 ms | index top k using filter |
| marketplace | 5,397 | 5.33% | exact | 1.000 | 0 / 735 | 14.9 ms | 17.5 ms | exact |
| marketplace | 5,397 | 5.33% | post | 0.344 | 22 / 735 | 17.4 ms | 20.4 ms | index top k |
| marketplace | 5,397 | 5.33% | pre | 0.822 | 99 / 735 | 16.2 ms | 18.8 ms | index top k using filter |
| marketplace | 5,397 | 5.33% | pre_full | 0.999 | 0 / 735 | 38.5 ms | 45.2 ms | index top k using filter |
| nike | 604 | 0.60% | default | 1.000 | 0 / 735 | 12.8 ms | 15.4 ms | exact |
| nike | 604 | 0.60% | post | 0.086 | 393 / 735 | 17.0 ms | 19.9 ms | index top k |
| nike | 604 | 0.60% | pre | 0.242 | 557 / 735 | 12.4 ms | 15.9 ms | index top k using filter |
| nike | 604 | 0.60% | pre_full | 1.000 | 0 / 735 | 47.8 ms | 51.1 ms | index top k using filter |
| none | 101,341 | 100.00% | default, tail run | 0.990 | 0 / 735 | 15.5 ms | 18.4 ms | index top k |
| none | 101,341 | 100.00% | default | 0.990 | 0 / 735 | 15.2 ms | 18.0 ms | index top k |
| small_brand | 10 | 0.01% | default | 1.000 | 0 / 735 | 12.2 ms | 14.8 ms | exact |
| small_brand | 10 | 0.01% | post | 0.011 | 702 / 735 | 16.7 ms | 19.6 ms | index top k |
| small_brand | 10 | 0.01% | pre | 0.017 | 720 / 735 | 11.8 ms | 14.2 ms | index top k using filter |
| small_brand | 10 | 0.01% | pre_full | 1.000 | 0 / 735 | 47.1 ms | 49.9 ms | index top k using filter |

