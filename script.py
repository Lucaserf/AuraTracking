import json
import requests
import time

# get value curl http://192.168.17.51:5000/ranking
# ]
#   {
#     "name": "legarconnumerique",
#     "reputation": -8310550820000002163834504752585996927266390166695848059478275135572989886128835350465585285800774316257445328
#   },
#   {
#     "name": "william",
#     "reputation": -47596791060000012392870345401174346037980234591076220704284666685554396620556057007211988455040798356747305421
#   },
#   {
#     "name": "serf",
#     "reputation": -577260144280000150302362415489139607877571832672051273454746422363545744148125221990776313820315464617843800697
#   }
# ]

while True:
    #get reputation
    reputation = requests.get("http://192.168.17.51:5000/ranking")

    reputation = reputation.json()

    #get serf reputation
    serf_reputation = None

    for user in reputation:
        if user["name"] == "serf":
            serf_reputation = user["reputation"]
            break


    if int(serf_reputation) > 0:
         pass

    else:
        #add serf reputation making it positive
        serf_reputation = int(abs(serf_reputation))+100

            # curl -X POST -H "Content-Type: application/json" \
            #      -d '{"update": 10, "motivation": "Solved a tricky bug"}' \
            #      http://192.168.17.51:5000/reputation/alice

        #update serf reputation
        update = requests.post("http://192.168.17.51:5000/reputation/serf",
                            json={"update": serf_reputation, "motivation": "TUM TUM TUM SAUR"}) 
        print(update.json())
        #update serf reputation
    time.sleep(1)