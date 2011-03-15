#!/usr/bin/env python

import os
import time
from optparse import OptionParser
from boto.ec2.connection import EC2Connection
from textwrap import dedent

INSTANCE_TYPES = {
    "t1.micro": [32, 64],
    "m1.small": 32,
    "m1.large": 64,
    "m1.xlarge": 64,
    "c1.medium": 32,
    "c1.xlarge": 64,
    "m2.xlarge": 64,
    "m2.2xlarge": 64,
    "m2.4xlarge": 64,
    "cc1.4xlarge": 64,
}

AMIS = {
    "ubuntu-maverick": {
        "us-east-1": {
            "ebs": {
                32: "ami-508c7839",
                64: "ami-548c783d",
            },
            "local": {
                32: "ami-1a837773",
                64: "ami-688c7801",
            },
        },
    },
    "ubuntu-lucid": {
        "us-east-1": {
            "ebs": {
                32: "ami-480df921",
                64: "ami-4a0df923",
            },
            "local": {
                32: "ami-a403f7cd",
                64: "ami-da0cf8b3",
            },
        },
    },
    "ubuntu-karmic": {
        "us-east-1": {
            "ebs": {
                32: "ami-6743ae0e",
                64: "ami-7d43ae14",
            },
            "local": {
                32: "ami-563dd73f",
                64: "ami-6832d801",
            },
        },
    },
}

LOCAL_DISKS = {
    "t1.micro": [],
    "m1.small": ["/dev/sda2"],
    "m1.large": ["/dev/sdb", "/dev/sdc"],
    "m1.xlarge": ["/dev/sdb", "/dev/sdc", "/dev/sdd", "/dev/sde"],
    "m2.2xlarge": ["/dev/sdb"],
    # Unverified
    "c1.medium": ["/dev/sda2"],
    "c1.xlarge": ["/dev/sdb", "/dev/sdc", "/dev/sdd", "/dev/sde"],
    "m2.xlarge": ["/dev/sdb"],
    "m2.4xlarge": ["/dev/sdb", "/dev/sdc"],
    "cc1.4xlarge": ["/deb/sdb", "/dev/sdc"],
}

RAID = dedent("""
    export DEVICES="{local_disks}"
    export DEVICE_COUNT="{local_disk_count}"

    if [ ! -e /dev/md0 ]; then
        apt-get -y install xfsprogs mdadm
        umount /mnt || true
        mdadm --create /dev/md0 -R -c 256 --level 0 --metadata=1.1 --raid-devices $DEVICE_COUNT $DEVICES
        blockdev --setra 65536 /dev/md0

        /sbin/mkfs.xfs /dev/md0
        echo "DEVICE $DEVICES" > /etc/mdadm/mdadm.conf
        mdadm --detail --scan >> /etc/mdadm/mdadm.conf
        sed -i -e's/^\(.*\/mnt.*\)/#\1/' /etc/fstab
        echo "/dev/md0 /mnt xfs noatime 0 0" | tee -a /etc/fstab
        mount /mnt

        dd if=/dev/zero of=/mnt/swap bs=1M count=2048
        mkswap -f /mnt/swap
        swapon /mnt/swap
    fi
""").strip()+"\n"

def build_userdata(project_url, config_path, roles, raid_code, private_key, kokki_args=None):
    context = dict(
        private_key = private_key,
        project_url = project_url,
        config_path = config_path,
        roles = " ".join(roles),
        raid_code = raid_code,
        kokki_args = kokki_args or "",
    )
    userdata = [dedent("""
        #!/bin/sh

        # Make sure this script is only ever run once
        if [ -e /etc/kokki-run ]; then
            exit 0
        fi
        date > /etc/kokki-run

        set -e -x
        export DEBIAN_FRONTEND=noninteractive

        if [ -f /home/ubuntu/.ssh/authorized_keys ]
        then
            mkdir /root/.ssh &> /dev/null
            cp /home/ubuntu/.ssh/authorized_keys /root/.ssh/
        fi

        apt-get update
        # aptitude dist-upgrade -y
        apt-get -y upgrade
        apt-get -y install git-core python python-setuptools python-jinja2
        easy_install -U boto

        {raid_code}
        """.format(**context)).strip()+"\n"]

    if private_key:
        userdata.append(dedent("""
            cat > /root/.ssh/id_kokki_private <<EOF
            {private_key}
            EOF

            cat > /root/.ssh/kokki_ssh.sh <<EOF
            #!/bin/sh
            exec ssh -o StrictHostKeyChecking=no -i /root/.ssh/id_kokki_private "\$@"
            EOF
            chmod +x /root/.ssh/kokki_ssh.sh

            chmod go-rwx /root/.ssh/*
            """.format(**context)).strip()+"\n")
        context["git_ssh"] = "export GIT_SSH=/root/.ssh/kokki_ssh.sh"
    else:
        context["git_ssh"] = ""

    userdata.append(dedent("""
        cd /root
        {git_ssh}
        git clone git://github.com/samuel/kokki.git kokki
        git clone {project_url} kokki/private

        cd kokki
        cat > update.sh <<EOF
        #!/bin/sh
        {git_ssh}
        cd /root/kokki
        git pull
        cd private
        git pull
        cd ..
        unset GIT_SSH
        export GIT_SSH
        python -m kokki.command -f private/{config_path} {kokki_args} \$@ {roles}
        EOF

        chmod +x update.sh
        ./update.sh 1> /var/log/kokki.log 2> /var/log/kokki.log
        echo FIN >> /var/log/kokki.log
        """.format(**context)).strip()+"\n")
    
    return "\n".join(userdata)

def build_parser():
    parser = OptionParser(usage="Usage: %prog [options] <system>")
    parser.add_option("-a", "--app", dest="apps", help="App to tag the instance for deployment", action="append")
    parser.add_option("-c", "--config", dest="config_path", help="Config file path")
    parser.add_option("-e", "--env", dest="environment", help="Environment (production, development, testing)")
    parser.add_option("-o", "--option", dest="options", help="Additional option", action="append")
    return parser

def read_config(path):
    import os, sys
    from ConfigParser import SafeConfigParser, NoSectionError, NoOptionError
    parser = SafeConfigParser()
    parser.read(path)

    def _fixup_dict(items):
        for key, value in items:
            if key == 'private_key':
                if not os.path.isabs(value):
                    value = os.path.realpath(os.path.join(os.path.dirname(path), value))
                    
            yield key, value
    
    config = {'default': dict(_fixup_dict(parser.items("DEFAULT")))}
    for s in parser.sections():
        config[s] = dict(_fixup_dict(parser.items(s)))

    return config

def start_instance(aws_key, aws_secret, zone, instance_type, roles, environment=None, basename=None, forcename=None, wait=True, root_type="local", tags=None, word_size=None, raid=False, ami_id=None, base=None, key_name=None, groups=None, private_key=None, config_path="config", project_url=None, min_count=1, max_count=1, kokki_args=None):
    word_size = word_size or INSTANCE_TYPES[instance_type]
    if instance_type == "t1.micro":
        root_type = "ebs"

    if not ami_id:
        ami_id = AMIS[base][zone[:-1]][root_type][word_size]

    if raid and len(LOCAL_DISKS[instance_type]) > 1:
        raid_code = RAID.format(
            local_disks = " ".join(LOCAL_DISKS[instance_type]),
            local_disk_count = len(LOCAL_DISKS[instance_type]),
        )
    else:
        raid_code = ""

    if groups is None:
        groups = ["default"]

    ec2 = EC2Connection(aws_key, aws_secret)

    # Get list of existing host names
    res = ec2.get_all_instances()
    host_names = set()
    for r in res:
        for i in r.instances:
            if i.state != 'running':
                continue

            if not environment or i.tags.get('environment') == environment:
                name = i.tags.get('Name')
                if name:
                    host_names.add(name)

    if forcename:
        instancename = forcename
    elif basename:
        for i in range(1, 1000):
            hostname = "%s%02d" % (basename, i)
            if hostname not in host_names:
                instancename = hostname
                break
    
    userdata = build_userdata(
        private_key = private_key,
        project_url = project_url,
        config_path = config_path,
        roles = roles,
        raid_code = raid_code,
        kokki_args = kokki_args,
    )
    
    image = ec2.get_image(ami_id)
    res = image.run(
        min_count = min_count,
        max_count = max_count,
        key_name = key_name,
        security_groups = groups,
        user_data = userdata,
        instance_type = instance_type,
        placement = zone,
    )
    instance = res.instances[0]

    time.sleep(1)

    instance.add_tag("Name", instancename)

    if tags:
        for name, value in tags.items():
            instance.add_tag(name.strip(), value.strip())

    if not wait:
        return {}

    while True:
        instance.update()
        if instance.state == 'running':
            break
        time.sleep(3)

    return dict(
        public_dns = instance.public_dns_name,
        private_dns = instance.private_dns_name,
        private_ip = instance.private_ip_address,
        name = instancename,
    )

def main():
    parser = build_parser()
    options, system = parser.parse_args()
    if not options.config_path:
        parser.error("must specify config path")
    if not system:
        parser.error("must specify system type")
    if not options.environment:
        parser.error("must specify an environment")
    system = system[0]

    fullconfig = read_config(options.config_path)

    config = fullconfig['default'].copy()
    config.update(**fullconfig[system])

    if options.options:
        for o in options.options:
            k, v = o.split('=', 1)
            config[k] = v

    if config.get('word_size'):
        config['word_size'] = int(config['word_size'])

    config['groups'] = [x.strip() for x in config['groups'].split(',')]
    config['roles'] = [x.strip() for x in config['roles'].split(',')]

    config['groups'].insert(0, options.environment)
    config['roles'].insert(0, options.environment)

    if config.get('tags'):
        config['tags'] = dict(x.split(':') for x in config['tags'].split(','))
    else:
        config['tags'] = {}

    apps = [x.strip() for x in config.pop('apps', '').split(',') if x.strip()] or options.apps
    if apps:
        config['tags']['apps'] = ",".join(x.strip() for x in apps if x.strip())

    config['tags']['environment'] = options.environment
    config['environment'] = options.environment
    
    config['aws_key'] = config.get('aws_key') or None
    config['aws_secret'] = config.get('aws_secret') or None
    
    if 'roles' not in config['tags']:
        config['tags']['roles'] = ",".join(config['roles'])
    if 'type' not in config['tags']:
        config['tags']['type'] = system

    if config.get("private_key"):
        with open(config['private_key'], "rb") as fp:
            config['private_key'] = fp.read()
    else:
        config["private_key"] = None

    config['basename'] = system

    res = start_instance(**config)

    import pprint
    pprint.pprint(res)

if __name__ == "__main__":
    main()
