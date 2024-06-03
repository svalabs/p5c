import random
import string
import uuid

import survey
from kubernetes import client, config

# Configs can be set in Configuration class directly or using helper utility
config.load_kube_config()

v1 = client.CoreV1Api()
custom = client.CustomObjectsApi()


def select_resource(resource_type, filter_function, message):
    ret = custom.list_cluster_custom_object(group="kubermatic.k8c.io", version="v1", plural=resource_type)
    resources = [resource for resource in ret['items'] if filter_function(resource)]
    resource_names = [resource['spec'][resource_type == 'users' and 'email' or 'name'] for resource in resources]

    if not resources:
        print(f"There are no {resource_type} that meet your criteria!")
        exit()

    index = survey.routines.select(message, options=resource_names, focus_mark='> ',
                                   evade_color=survey.colors.basic('yellow'))
    return resources[index]


def create_binding(project, user, user_type):
    return {
        "apiVersion": "kubermatic.k8c.io/v1",
        "kind": "UserProjectBinding",
        "metadata": {"generation": 1, "name": generate_random_name()},
        "spec": {
            "group": f"{user_type}-{project['metadata']['name']}",
            "projectID": project['metadata']['name'],
            "userEmail": user['spec']['email']
        }
    }


def generate_random_name():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))


def select_admin():
    return select_resource("users", lambda user: user['spec']['admin'], 'Which admin do you want to add? ')


def select_non_admin():
    return select_resource("users", lambda user: not user['spec']['admin'], 'Which user do you want to promote? ')


def select_project(filter=[]):
    return select_resource("projects", lambda project: project['metadata']['name'] not in filter,
                           'Which project do you want to work on? ')


def add_member():
    admin = select_admin()
    ret = custom.list_cluster_custom_object(group="kubermatic.k8c.io", version="v1", plural="userprojectbindings")
    bindings = [binding for binding in ret['items'] if binding['spec']['userEmail'] == admin['spec']['email']]
    existing_projects = [project['spec']['projectID'] for project in bindings]
    project = select_project(existing_projects)
    binding = {
        "apiVersion": "kubermatic.k8c.io/v1",
        "kind": "UserProjectBinding",
        "metadata": {
            "finalizers": [
                "kubermatic.k8c.io/cleanup-seed-user-project-bindings"
            ],
            "generation": 1,
            "name": ''.join(random.choices(string.ascii_lowercase + string.digits, k=10)),
            "ownerReferences": [
                {
                    "apiVersion": "kubermatic.k8c.io/v1",
                    "kind": "Project",
                    "name": project['metadata']['name'],
                    "uid": project['metadata']['uid']
                }
            ],
            "uid": str(uuid.uuid4())
        },
        "spec": {
            "group": f"owners-{project['metadata']['name']}",
            "projectID": project['metadata']['name'],
            "userEmail": admin['spec']['email']
        }
    }
    custom.create_cluster_custom_object(group="kubermatic.k8c.io", version="v1", plural="userprojectbindings",
                                        body=binding)


def make_admin():
    user = select_non_admin()
    patch = {
        "spec": {"admin": True}
    }
    custom.patch_cluster_custom_object(group="kubermatic.k8c.io", version="v1", plural="users",
                                       name=user['metadata']['name'], body=patch)


def make_non_admin():
    admin = select_admin()
    patch = {
        "spec": {"admin": False}
    }
    custom.patch_cluster_custom_object(group="kubermatic.k8c.io", version="v1", plural="users",
                                       name=admin['metadata']['name'], body=patch)


def remove_member():
    project = select_project()
    ret = custom.list_cluster_custom_object(group="kubermatic.k8c.io", version="v1", plural="userprojectbindings")
    bindings = [binding for binding in ret['items'] if binding['spec']['projectID'] == project['metadata']['name']]
    user_names = [binding['spec']['userEmail'] for binding in bindings]
    index = survey.routines.select('Which user do you want to remove? ', options=user_names, focus_mark='> ',
                                   evade_color=survey.colors.basic('yellow'))
    binding = bindings[index]
    custom.delete_cluster_custom_object(group="kubermatic.k8c.io", version="v1", plural="userprojectbindings",
                                        name=binding['metadata']['name'])


mode_list = ["Make someone admin", "Make someone a regular user", "Add an admin to a project",
             "Remove user from project"]

index = survey.routines.select('What do you want to do? ', options=mode_list, focus_mark='> ',
                               evade_color=survey.colors.basic('yellow'))

if index == 0:
    make_admin()
elif index == 1:
    make_non_admin()
elif index == 2:
    add_member()
elif index == 3:
    remove_member()
else:
    print("Bad choice!")
