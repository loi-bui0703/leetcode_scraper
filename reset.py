import pickle

# Clear track.conf
with open("track.conf", "w") as f:
    f.write("-1")

# Clear out.html
with open("out.html", "w") as f:
    f.write("")

# Clear chapters.pickle
with open("chapters.pickle", "wb") as f:
    pickle.dump([], f)

print("Reset successfully")
