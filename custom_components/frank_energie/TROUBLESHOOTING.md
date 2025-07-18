# Frank Energie Integration Troubleshooting

## Recent Changes Made to Fix GraphQL Validation Error

### 1. Updated Library Version and API Compatibility
- Updated `python-frank-energie` from version `6.0.0` to `>=2025.6.19,<2025.7.0` in `manifest.json`
- Version `2025.6.19` specifically fixes GraphQL issues by removing problematic fields from the `me` query
- Updated integration code to handle API structure changes in the newer library version
- The integration now gracefully handles cases where site-specific information isn't available and falls back to public prices

### 2. Enhanced Error Handling in `coordinator.py`
- Added support for handling `FrankEnergieException` in addition to `RequestException` and `AuthException`
- Improved fallback logic to use public prices when user-specific prices fail due to GraphQL validation errors
- Added better handling for missing site references
- Enhanced logging to help identify whether the integration is using user-specific or public prices
- Added graceful handling when month summary or invoice data isn't available

### 3. Enhanced Error Handling in `__init__.py`
- Added comprehensive error handling around the `api.me()` call during setup
- Added specific detection for GraphQL validation errors
- Improved logging to help debug authentication and API issues
- Added fallback behavior when site information cannot be retrieved initially

### 4. Improved Config Flow and Authentication
- Enhanced config flow with better error handling for authentication failures
- Added proper type annotations and documentation to improve code quality
- Improved reauth flow to handle expired tokens more gracefully  
- Added better parameter handling in config flow methods
- Enhanced logging in authentication steps to help debug login issues

### 5. Better Authentication Flow
- Authentication errors now trigger proper reauth flows instead of hard failures
- More informative error messages for debugging
- Graceful handling of temporary API issues

## Common Issues and Solutions

### GraphQL Validation Error
**Symptoms:** Error message contains "Graphql validation error"

**Possible Causes:**
1. **Outdated authentication tokens** - The tokens may have expired or been invalidated
2. **API changes** - Frank Energie may have updated their API
3. **Network connectivity issues** - Temporary connection problems

**Solutions:**
1. **Reconfigure the integration:**
   - Go to Settings → Devices & Services
   - Find the Frank Energie integration
   - Click "Configure" and re-enter your credentials

2. **Restart Home Assistant:**
   - Sometimes a simple restart resolves temporary API issues

3. **Check your Frank Energie account:**
   - Ensure your account is active and has delivery sites in "IN_DELIVERY" status
   - Verify your login credentials work on the Frank Energie website

### No Suitable Sites Found
**Symptoms:** Error message "No suitable sites found for this account"

**Possible Causes:**
- Your delivery sites are not in "IN_DELIVERY" status
- Account has no associated delivery addresses

**Solutions:**
1. Check your Frank Energie account online to ensure you have active delivery sites
2. Contact Frank Energie if your sites should be active but aren't showing as "IN_DELIVERY"

### FrankEnergieException Errors
**Symptoms:** Error message contains "FrankEnergieException" and "Graphql validation error"

**Possible Causes:**
- The user_prices API call is failing due to GraphQL validation errors
- Site reference is missing or invalid
- API changes in the Frank Energie service

**Solutions:**
1. The integration now automatically falls back to public prices when user prices fail
2. Check the logs to see if the integration is successfully using public prices instead
3. If the issue persists, try reconfiguring the integration to refresh authentication
4. The integration will continue to work using public pricing data even when user-specific pricing fails

### API Structure Changes
**Symptoms:** AttributeError about missing 'deliverySites' attribute

**Possible Causes:**
- The newer library version has changed the API response structure
- The `Me` object no longer contains delivery site information directly

**Solutions:**
1. The integration has been updated to handle this change gracefully
2. If you continue to see this error, restart Home Assistant to ensure the new code is loaded
3. The integration will still work by using public prices instead of user-specific prices

### Configuration Flow Issues
**Symptoms:** Errors during initial setup or reconfiguration of the integration

**Possible Causes:**
- Network connectivity issues during authentication
- Invalid credentials
- Frank Energie API changes affecting the login process

**Solutions:**
1. **Verify your credentials:**
   - Ensure your username and password are correct
   - Test logging in to the Frank Energie website directly
   
2. **Check network connectivity:**
   - Ensure Home Assistant can reach the Frank Energie API
   - Check for any firewall or proxy issues
   
3. **Try the authentication flow again:**
   - The config flow now has better error handling and will provide more specific error messages
   - Look for specific error messages in the configuration UI

4. **Use public pricing mode:**
   - If authentication continues to fail, you can set up the integration without authentication
   - This will provide public pricing data instead of user-specific pricing

### Authentication Flow Improvements
**Recent Changes:**
- Enhanced error handling in the login process
- Better type annotations and parameter handling
- Improved reauth flow when tokens expire
- More descriptive error messages during configuration

**Benefits:**
- More reliable authentication process
- Better user experience during setup
- Clearer error messages when authentication fails
- Graceful handling of expired tokens

### Dependency Conflicts
**Symptoms:** Error message about dependency resolution failures, "requests" version conflicts

**Possible Causes:**
- Newer library versions have incompatible dependency requirements
- Home Assistant uses specific versions of dependencies that conflict with newer library versions

**Solutions:**
1. The integration now uses version `>=2025.6.19,<2025.7.0` which should be compatible
2. If dependency issues persist, you can try manually specifying an older compatible version
3. Check if your Home Assistant version is up to date
**Symptoms:** Repeated authentication failures or reauth requests

**Possible Causes:**
- Frank Energie has changed their authentication system
- Network issues preventing token renewal

**Solutions:**
1. Delete and re-add the integration completely
2. Check your internet connection
3. Verify your Frank Energie account credentials

## Debug Information

To get more detailed debug information, add this to your `configuration.yaml`:

```yaml
logger:
  default: warning
  logs:
    custom_components.frank_energie: debug
    python_frank_energie: debug
```

Then restart Home Assistant and check the logs for more detailed error information.

## Reporting Issues

If problems persist after trying these solutions, please:

1. Enable debug logging (see above)
2. Reproduce the issue
3. Collect the relevant log entries
4. Report the issue with the log details

The integration now provides much more detailed logging to help identify the root cause of issues.
