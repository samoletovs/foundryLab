$query = "[?contains(roleName,'AI') || contains(roleName,'Cognitive Services User')].{name:roleName,id:name}"
az role definition list --query $query -o table
