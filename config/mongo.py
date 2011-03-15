
def mongo(kit):
    kit.update_config({
        "mongodb.replica_set": "primary",
    })
    kit.include_recipe("mongodb")
