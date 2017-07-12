"""
    Code that handle spark configuration
"""
import time
import os
import json
import shutil
from subprocess import call, Popen
from typing import List
import azure.batch.models as batchmodels
from core import config
from install import pick_master

batch_client = config.batch_client
spark_home = "/dsvm/tools/spark/current"
spark_conf_folder = os.path.join(spark_home, "conf")


def get_pool() -> batchmodels.CloudPool:
    return batch_client.pool.get(config.pool_id)


def get_node(node_id: str) -> batchmodels.ComputeNode:
    return batch_client.compute_node.get(config.pool_id, node_id)


def list_nodes() -> List[batchmodels.ComputeNode]:
    """
        List all the nodes in the pool.
    """
    # TODO use continuation token & verify against current/target dedicated of
    # pool
    return batch_client.compute_node.list(config.pool_id)


def wait_for_pool_ready() -> batchmodels.CloudPool:
    """
        Wait for the pool to have allocated all the nodes
    """
    while True:
        pool = get_pool()
        if pool.allocation_state == batchmodels.AllocationState.steady:
            return pool
        else:
            print("Waiting for pool to be steady. It is currently %s" %
                  pool.allocation_state)
            time.sleep(5)  # Sleep for 10 seconds before trying again


def setup_connection():
    """
        This setup spark config with which nodes are slaves and which are master
    """
    wait_for_pool_ready()

    master_node_id = pick_master.get_master_node_id(
        batch_client.pool.get(config.pool_id))
    master_node = get_node(master_node_id)
    
    master_file = open(os.path.join(spark_conf_folder, "master"), 'w')

    print("Adding master node ip to config file '%s'" % master_node.ip_address)
    master_file.write("%s\n" % master_node.ip_address)

    master_file.close()


def generate_jupyter_config():
    master_node = get_node(config.node_id)
    master_node_ip = master_node.ip_address

    return dict(
        display_name="PySpark",
        language="python",
        argv=[
            "/usr/bin/python3",
            "-m",
            "ipykernel",
            "-f",
            "{connection_file}",
        ],
        env=dict(
            SPARK_HOME="/dsvm/tools/spark/current",
            PYSPARK_PYTHON="/usr/bin/python3",
            PYSPARK_SUBMIT_ARGS="--master spark://%s:7077 pyspark-shell" % master_node_ip,
        )
    )


def setup_jupyter():
    print("Setting up jupyter.")
    call(["/anaconda/envs/py35/bin/jupyter", "notebook", "--generate-config"])

    jupyter_config_file = os.path.join(os.path.expanduser(
        "~"), ".jupyter/jupyter_notebook_config.py")

    with open(jupyter_config_file, "a") as config_file:
        config_file.write('\n')
        config_file.write('c.NotebookApp.token=""\n')
        config_file.write('c.NotebookApp.password=""\n')
    shutil.rmtree('/usr/local/share/jupyter/kernels')
    os.makedirs('/usr/local/share/jupyter/kernels/pyspark', exist_ok=True)

    with open('/usr/local/share/jupyter/kernels/pyspark/kernel.json', 'w') as outfile:
        data = generate_jupyter_config()
        json.dump(data, outfile, indent=2)


def start_jupyter():
    jupyter_port = config.jupyter_port

    my_env = os.environ.copy()
    my_env["PYSPARK_DRIVER_PYTHON"] = "/anaconda/envs/py35/bin/jupyter"
    my_env["PYSPARK_DRIVER_PYTHON_OPTS"] = "notebook --no-browser --port='%s'" % jupyter_port

    print("Starting pyspark")
    process = Popen(["pyspark"], env=my_env)
    print("Started pyspark with pid %s" % process.pid)


def wait_for_master():
    print("Waiting for master to be ready.")
    master_node_id = pick_master.get_master_node_id(
        batch_client.pool.get(config.pool_id))

    if master_node_id == config.node_id:
        return

    while True:
        master_node = get_node(master_node_id)

        if master_node.state in [batchmodels.ComputeNodeState.idle, batchmodels.ComputeNodeState.running]:
            break
        else:
            print("Still waiting on master")
            time.sleep(10)


def start_spark_master():
    master_ip = get_node(config.node_id).ip_address
    exe = os.path.join(spark_home, "sbin", "start-master.sh")
    cmd = [exe, "-h", master_ip]
    print("Starting master with '%s'" % " ".join(cmd))
    call(cmd)

    setup_jupyter()
    start_jupyter()


def start_spark_worker():
    wait_for_master()
    exe = os.path.join(spark_home, "sbin", "start-slave.sh")
    master_node_id = pick_master.get_master_node_id(
        batch_client.pool.get(config.pool_id))
    master_node = get_node(master_node_id)

    my_env = os.environ.copy()
    my_env["SPARK_MASTER_IP"] = master_node.ip_address

    cmd = [exe, "spark://%s:7077" % master_node.ip_address]
    print("Connecting to master with '%s'" % " ".join(cmd))
    call(cmd)
