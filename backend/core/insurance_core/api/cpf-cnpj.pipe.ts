import { Pipe, PipeTransform } from '@angular/core';

@Pipe({ name: 'cpfCnpj' })
export class CpfCnpjPipe implements PipeTransform {
  transform(value: string | number | undefined): string {
    if (!value) return '';
    const val = value.toString().replace(/\D/g, '');
    
    if (val.length === 11) {
      return val.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, '$1.$2.$3-$4');
    } else if (val.length === 14) {
      return val.replace(/(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})/, '$1.$2.$3/$4-$5');
    }
    return value.toString();
  }
}