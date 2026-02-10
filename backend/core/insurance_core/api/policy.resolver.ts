import { Injectable } from '@angular/core';
import { Resolve, ActivatedRouteSnapshot } from '@angular/router';
import { Observable } from 'rxjs';
import { PolicyService, Policy } from './policy.service';

@Injectable({
  providedIn: 'root'
})
export class PolicyResolver implements Resolve<Policy> {
  constructor(private service: PolicyService) {}

  resolve(route: ActivatedRouteSnapshot): Observable<Policy> {
    return this.service.get(route.params['id']);
  }
}