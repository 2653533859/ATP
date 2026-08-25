import { describe, expect, it } from 'vitest'

import { buildMobileApkOptions, findMobileApkPackage } from './mobileSpecialForm'

describe('mobile special form helpers', () => {
  it('only exposes APKs with confirmed package names', () => {
    const options = buildMobileApkOptions([
      { id: 1, filename: 'karing.apk', package_name: '  com.example.karing  ', version_name: ' 1.0.0 ' },
      { id: 2, filename: 'unknown.apk', package_name: null },
      { id: 3, filename: 'empty.apk', package_name: '  ' },
    ])

    expect(options).toEqual([{
      label: 'com.example.karing · karing.apk · v1.0.0',
      value: 1,
      packageName: 'com.example.karing',
      filename: 'karing.apk',
    }])
  })

  it('resolves the selected package for automatic binding', () => {
    const options = buildMobileApkOptions([{ id: 1, filename: 'app.apk', package_name: 'com.example.app' }])

    expect(findMobileApkPackage(options, 1)).toBe('com.example.app')
    expect(findMobileApkPackage(options, null)).toBe('')
    expect(findMobileApkPackage(options, 404)).toBe('')
  })
})
