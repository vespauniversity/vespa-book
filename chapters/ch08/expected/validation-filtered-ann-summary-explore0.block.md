| rung | documents | share | strategy | agreement@100 | empty queries | p50 | p95 | algorithm |
|---|---|---|---|---|---|---|---|---|
| has_brand | 95,944 | 94.67% | default | 0.910 | 0 / 735 | 13.2 ms | 15.9 ms | index top k using filter |
| has_brand | 95,944 | 94.67% | post | 0.874 | 0 / 735 | 13.6 ms | 16.2 ms | index top k |
| has_brand | 95,944 | 94.67% | pre | 0.910 | 0 / 735 | 13.7 ms | 16.3 ms | index top k using filter |
| has_description | 51,995 | 51.31% | default | 0.919 | 0 / 735 | 13.8 ms | 16.6 ms | index top k using filter |
| has_description | 51,995 | 51.31% | exact | 1.000 | 0 / 735 | 17.4 ms | 20.0 ms | exact |
| has_description | 51,995 | 51.31% | post | 0.860 | 0 / 735 | 14.0 ms | 16.7 ms | index top k |
| has_description | 51,995 | 51.31% | pre | 0.919 | 0 / 735 | 14.2 ms | 17.0 ms | index top k using filter |
| marketplace | 5,397 | 5.33% | default | 0.697 | 99 / 735 | 13.5 ms | 16.2 ms | index top k using filter |
| marketplace | 5,397 | 5.33% | exact | 1.000 | 0 / 735 | 14.9 ms | 17.5 ms | exact |
| marketplace | 5,397 | 5.33% | post | 0.342 | 22 / 735 | 16.9 ms | 19.9 ms | index top k |
| marketplace | 5,397 | 5.33% | pre | 0.697 | 99 / 735 | 13.9 ms | 16.8 ms | index top k using filter |
| marketplace | 5,397 | 5.33% | pre_full | 0.964 | 0 / 735 | 25.4 ms | 33.5 ms | index top k using filter |
| nike | 604 | 0.60% | default | 1.000 | 0 / 735 | 12.8 ms | 15.4 ms | exact |
| nike | 604 | 0.60% | post | 0.085 | 395 / 735 | 16.6 ms | 19.5 ms | index top k |
| nike | 604 | 0.60% | pre | 0.242 | 557 / 735 | 12.3 ms | 15.2 ms | index top k using filter |
| nike | 604 | 0.60% | pre_full | 0.995 | 0 / 735 | 36.2 ms | 45.0 ms | index top k using filter |
| none | 101,341 | 100.00% | default, tail run | 0.908 | 0 / 735 | 14.0 ms | 16.8 ms | index top k |
| none | 101,341 | 100.00% | default | 0.908 | 0 / 735 | 13.8 ms | 16.3 ms | index top k |
| small_brand | 10 | 0.01% | default | 1.000 | 0 / 735 | 11.7 ms | 14.3 ms | exact |
| small_brand | 10 | 0.01% | post | 0.011 | 701 / 735 | 16.4 ms | 19.2 ms | index top k |
| small_brand | 10 | 0.01% | pre | 0.017 | 720 / 735 | 11.7 ms | 14.3 ms | index top k using filter |
| small_brand | 10 | 0.01% | pre_full | 1.000 | 0 / 735 | 47.2 ms | 49.8 ms | index top k using filter |

