
import os.path

def base(kit):
    kit.add_cookbook_path(
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cookbooks"),
        "kokki.cookbooks")
    kit.update_config({
        "users": {
            "samuel": dict(
                id = 1010,
                groups = ["sysadmin", "adm"],
                password = "$1$Xwxr1Cnz$RskDumw.hMaWE76JW0lQD/",
                sshkey_id = "samuel",
                sshkey_type = "ssh-rsa",
                sshkey = "AAAAB3NzaC1yc2EAAAABIwAAAQEAzss92sZVM13Zg/NmGBPC9mdmlf1KBQ37On/dY83YoD0JKCwz6Z9mC/zplmTZRB59AzVKMITHvRAXPSQnpGzzTcdzpRS+0FesoR751mKANR40Wuohk0Wd/bLtPUN11A1AMttOrZEdpmaaGubZ/INreZxTQPwkCzz7e1SgCdLlQDyaRTgPZLkrYd6TelPi1oHHRIj09jlusOVB84vYkU52wyN1fzLVMO60BvydCjaH2Vs1sKucs0q3x1Km/KbeTiMzT1WUR4IJR/0O5Q0MVnQ3yy/h0NUpJgOitGumnVe5FSrXQoma9Yz6fDJupxlG83I5IeP9VwwmZNhv6O+Q/ygVEQ==",
            ),
        },
        "limits": [
            dict(domain="mongodb", type="soft", item="nofile", value="10000"),
            dict(domain="mongodb", type="hard", item="nofile", value="10000"),
            dict(domain="nginx", type="soft", item="nofile", value="10000"),
            dict(domain="nginx", type="hard", item="nofile", value="10000"),
            dict(domain="www-data", type="soft", item="nofile", value="10000"),
            dict(domain="www-data", type="hard", item="nofile", value="10000"),
            dict(domain="root", type="soft", item="nofile", value="30000"),
            dict(domain="root", type="hard", item="nofile", value="30000"),
        ],
    })
    kit.include_recipe("users", "sudo", "limits", "twitbook")
