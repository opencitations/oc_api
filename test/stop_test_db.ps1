$CONTAINER_NAME = "virtuoso-test-api"

$runningContainer = docker ps -q -f name=$CONTAINER_NAME
if ($runningContainer) {
    docker stop $CONTAINER_NAME
}

$existingContainer = docker ps -aq -f name=$CONTAINER_NAME
if ($existingContainer) {
    docker rm $CONTAINER_NAME
} 