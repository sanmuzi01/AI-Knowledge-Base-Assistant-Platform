export type ToastType = 'success' | 'error' | 'info'

export interface ToastMessage {
  id: number
  type: ToastType
  message: string
}

export const toast = (type: ToastType, message: string) => {
  window.dispatchEvent(new CustomEvent('app-toast', { detail: { type, message } }))
}

export const toastSuccess = (message: string) => toast('success', message)
export const toastError = (message: string) => toast('error', message)
export const toastInfo = (message: string) => toast('info', message)
