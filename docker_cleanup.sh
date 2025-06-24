#!/bin/bash

# Docker cleanup script for zgdk project

echo "🧹 ZGDK Docker Cleanup Script"
echo "=============================="

# Function to show current Docker usage
show_usage() {
    echo "📊 Current Docker usage:"
    docker system df
    echo ""
}

# Function to cleanup old containers and images
cleanup_all() {
    echo "🗑️  Removing stopped containers..."
    docker container prune -f
    
    echo "🗑️  Removing unused images..."
    docker image prune -f
    
    echo "🗑️  Removing unused volumes..."
    docker volume prune -f
    
    echo "🗑️  Removing unused networks..."
    docker network prune -f
    
    echo "🗑️  Removing build cache..."
    docker builder prune -f
}

# Function to cleanup ZGDK specific images
cleanup_zgdk() {
    echo "🗑️  Removing old ZGDK images..."
    docker images | grep zgdk | grep -v latest | awk '{print $3}' | xargs -r docker rmi -f
}

# Function to restart ZGDK services
restart_services() {
    echo "🔄 Restarting ZGDK services..."
    docker-compose down
    docker-compose up -d --build
}

# Main menu
case "$1" in
    "usage")
        show_usage
        ;;
    "all")
        show_usage
        cleanup_all
        show_usage
        ;;
    "zgdk")
        show_usage
        cleanup_zgdk
        show_usage
        ;;
    "restart")
        restart_services
        ;;
    "full")
        show_usage
        echo "⚠️  Full cleanup - removing everything except running containers..."
        read -p "Are you sure? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            docker-compose down
            cleanup_all
            cleanup_zgdk
            show_usage
        fi
        ;;
    *)
        echo "Usage: $0 {usage|all|zgdk|restart|full}"
        echo ""
        echo "Commands:"
        echo "  usage   - Show current Docker disk usage"
        echo "  all     - Clean unused containers, images, volumes, networks"
        echo "  zgdk    - Clean old ZGDK images only"
        echo "  restart - Restart ZGDK services"
        echo "  full    - Full cleanup (stops services first)"
        echo ""
        echo "Examples:"
        echo "  ./docker_cleanup.sh usage"
        echo "  ./docker_cleanup.sh all"
        echo "  ./docker_cleanup.sh full"
        exit 1
        ;;
esac 