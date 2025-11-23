# Persist car location across restarts

# Create a pyscript entity that persists
# Default to RBKC Town Hall as a central location
state.persist('pyscript.car_location_backup', default_value='Town Hall, Hornton Street')

@time_trigger('startup')
def restore_car_location():
    """Restore car location on startup"""
    # Wait a moment for input_text to be ready
    task.sleep(2)
    backup = pyscript.car_location_backup
    if backup and backup != 'unknown':
        log.info(f"🚗 Restoring car location: {backup}")
        state.set('input_text.car_current_street', backup)
    else:
        log.warning("No car location backup found")

@state_trigger('input_text.car_current_street')
def backup_car_location(value=None):
    """Backup car location when it changes"""
    if value:
        log.info(f"Backing up car location: {value}")
        pyscript.car_location_backup = value
        # Trigger parking re-check with new location
        log.info(f"Triggering parking re-check for new location: {value}")
        pyscript.check_parking(car_location=value)
