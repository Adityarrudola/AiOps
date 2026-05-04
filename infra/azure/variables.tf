variable "location" {
  type        = string
  default     = "eastus"
  description = "Azure region for demonstration infrastructure."
}

variable "acr_name" {
  type        = string
  default     = "aioobsacr001"
  description = "Name of the Azure Container Registry."
}
