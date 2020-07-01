#!/bin/bash

# This custom script only works on images where jupyter is pre-installed on the Docker image
#
# This custom script has been tested to work on the following docker images:
#  - aztk/python:spark2.2.0-python3.6.2-base
#  - aztk/python:spark2.2.0-python3.6.2-gpu
#  - aztk/python:spark2.1.0-python3.6.2-base
#  - aztk/python:spark2.1.0-python3.6.2-gpu

echo "Is master: $AZTK_IS_MASTER"

if  [ "$AZTK_IS_MASTER" = "true" ]; then
    pip install jupyter --upgrade
    pip install notebook --upgrade
    
    #PYSPARK_DRIVER_PYTHON="/opt/conda/bin/jupyter"
    #JUPYTER_KERNELS="/opt/conda/share/jupyter/kernels"
    export PYSPARK_DRIVER_PYTHON="/usr/local/bin/jupyter"
    export JUPYTER_KERNELS="/usr/local/share/jupyter/kernels"

    # disable password/token on jupyter notebook
    jupyter notebook --generate-config --allow-root
    JUPYTER_CONFIG='/root/.jupyter/jupyter_notebook_config.py'
    echo >> $JUPYTER_CONFIG
    #echo -e 'c.NotebookApp.token=""' >> $JUPYTER_CONFIG
    #echo -e 'c.NotebookApp.password="sha1:9bb8f81a031d:fad75863b765f2f51d9db5d3d7654e3d5640fd18"' >> $JUPYTER_CONFIG
    echo -e 'c.NotebookApp.allow_remote_access=True' >> $JUPYTER_CONFIG
    echo -e 'c.NotebookApp.base_url="/notebook/"' >> $JUPYTER_CONFIG
    echo -e 'c.NotebookApp.trust_xheaders=True' >> $JUPYTER_CONFIG
    echo -e 'c.NotebookApp.allow_origin='*' >> $JUPYTER_CONFIG

    # get master ip
    MASTER_IP=$(hostname -i)

    # remove existing kernels
    rm -rf $JUPYTER_KERNELS/*

    # set up jupyter to use pyspark
    mkdir $JUPYTER_KERNELS/pyspark
    touch $JUPYTER_KERNELS/pyspark/kernel.json
    cat << EOF > $JUPYTER_KERNELS/pyspark/kernel.json
{
    "display_name": "PySpark",
    "language": "python",
    "argv": [
        "python",
        "-m",
        "ipykernel",
        "-f",
        "{connection_file}"
    ],
    "env": {
        "SPARK_HOME": "$SPARK_HOME",
        "PYSPARK_PYTHON": "python",
        "PYSPARK_SUBMIT_ARGS": "--master spark://$AZTK_MASTER_IP:7077 pyspark-shell"
    }
}
EOF

    # start jupyter notebook from /mnt - this is where we recommend you put your azure files mount point as well
    cd /mnt
    (PYSPARK_DRIVER_PYTHON=$PYSPARK_DRIVER_PYTHON PYSPARK_DRIVER_PYTHON_OPTS="notebook --no-browser --port=8888 --allow-root" pyspark &)
fi


