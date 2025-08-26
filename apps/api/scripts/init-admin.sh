#!/bin/bash
# Convenience script for admin account management

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Change to API directory
cd "$API_DIR"

# Activate virtual environment if it exists
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
    echo "✓ Activated virtual environment"
fi

# Function to show usage
usage() {
    echo "Usage: $0 [command] [options]"
    echo ""
    echo "Commands:"
    echo "  create-admin     Create new system admin account"
    echo "  reset-password   Reset password for existing user"
    echo "  list-users       List all users in the system"
    echo ""
    echo "Examples:"
    echo "  $0 create-admin"
    echo "  $0 reset-password admin newpassword123"
    echo "  $0 list-users"
    echo ""
}

# Function to create admin with interactive prompts
create_admin() {
    echo "🔧 Creating new system admin account..."
    echo ""
    
    read -p "Username: " username
    read -p "Email: " email
    read -p "First Name [System]: " first_name
    read -p "Last Name [Admin]: " last_name
    
    # Hide password input
    echo -n "Password: "
    read -s password
    echo
    echo -n "Confirm Password: "
    read -s password_confirm
    echo
    
    if [ "$password" != "$password_confirm" ]; then
        echo "❌ Passwords do not match!"
        exit 1
    fi
    
    if [ -z "$password" ]; then
        echo "❌ Password cannot be empty!"
        exit 1
    fi
    
    # Set defaults
    first_name=${first_name:-"System"}
    last_name=${last_name:-"Admin"}
    
    echo ""
    echo "Creating admin user with:"
    echo "  Username: $username"
    echo "  Email: $email"
    echo "  Name: $first_name $last_name"
    echo ""
    
    python scripts/init_admin.py create \
        --username "$username" \
        --email "$email" \
        --password "$password" \
        --first-name "$first_name" \
        --last-name "$last_name"
}

# Main script logic
case "$1" in
    "create-admin")
        create_admin
        ;;
    "reset-password")
        if [ -z "$2" ] || [ -z "$3" ]; then
            echo "❌ Usage: $0 reset-password <username> <new-password>"
            exit 1
        fi
        python scripts/init_admin.py reset-password "$2" "$3"
        ;;
    "list-users")
        python scripts/init_admin.py list
        ;;
    *)
        usage
        exit 1
        ;;
esac