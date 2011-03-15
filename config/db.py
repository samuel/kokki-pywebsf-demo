
def db(kit):
    kit.update_config({
        "postgresql9.listen_addresses": ["*"],
    })
    kit.include_recipe("postgresql9.server")
