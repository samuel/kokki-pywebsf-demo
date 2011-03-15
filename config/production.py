
def production(kit):
    kit.update_config({
        "environment": "production",
    })
    base(kit)
